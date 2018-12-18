import random
import asyncio
import enchant
from discord.ext import commands
from datetime import datetime
import re

parentheses_re = re.compile(r'\(([-+*xX/ \d]+)\)')
multiplication_division_re = re.compile(r'(\d+) *([*xX/]) *(\d+)')
addition_subtraction_re = re.compile(r'(\d+) *([-+]) *(\d+)')
expression_start_re = re.compile(r'^[( ]*\d')
expression_end_re = re.compile(r'\d[) ]*$')
expression_simple_re = re.compile(r'^[-+*xX/ ()\d]+$')
number_re = re.compile(r'\d+')
letter_re = re.compile(r'\w+')
repeated_operator_re = re.compile(r'[-+*xX/]\D*[-+*xX/]')
dictionary = enchant.Dict("en_GB")

vowels_d = {'a':15, 'e': 21, 'i': 13, 'o': 13, 'u': 5}
consonants_d = {'b': 2, 'c': 3, 'd': 6, 'f': 2, 'g': 3, 'h': 2,
                'j': 1, 'k': 1, 'l': 5, 'm': 4, 'n': 8, 'p': 4,
                'q': 1, 'r': 9, 's': 9, 't': 9, 'v': 1, 'w': 1,
                'x': 1, 'y': 1, 'z': 1}


class NotIntegerDivision(ValueError):
    """Integer division results in a non-integer result."""
    pass


class NegativeResult(ValueError):
    """Subtraction results in a negative result."""
    pass


def multiply(a, b):
    return a * b


def divide(a, b):
    if a % b:
        raise NotIntegerDivision
    return a // b


def add(a, b):
    return a + b


def subtract(a, b):
    if a < b:
        raise NegativeResult
    return a - b


def multiply_or_divide(match):
    a = int(match.group(1))
    b = int(match.group(3))
    operator = match.group(2)
    if operator == "/":
        return str(divide(a, b))
    return str(multiply(a, b))


def add_or_subtract(match):
    a = int(match.group(1))
    b = int(match.group(3))
    operator = match.group(2)
    if operator == "+":
        return str(add(a, b))
    return str(subtract(a, b))


def calculate_individual(expression):
    replaced = 1
    while replaced:
        expression, replaced = multiplication_division_re.subn(multiply_or_divide, expression, count=1)
    replaced = 1
    while replaced:
        expression, replaced = addition_subtraction_re.subn(add_or_subtract, expression, count=1)
    return int(expression)


def replace_expression(match):
    return str(calculate_individual(match.group(1)))


def calculate(expression):
    replaced = 1
    while replaced:
        expression, replaced = parentheses_re.subn(replace_expression, expression)
    return calculate_individual(expression)


def is_valid_expression(expression):
    if not (expression_start_re.match(expression) and expression_end_re.search(expression) and
            expression_simple_re.match(expression)) or repeated_operator_re.search(expression):
        return False

    parentheses = 0
    for c in expression:
        if c == '(':
            parentheses += 1
        elif c == ')':
            parentheses -= 1
            if parentheses < 0:
                return False
    return True


def is_valid_word(word):
    return dictionary.check(word)


def uses_allowed_numbers(expression, allowed_numbers):
    allowed_numbers = {x: allowed_numbers.count(x) for x in allowed_numbers}
    for number in number_re.finditer(expression):
        number = int(number.group(0))
        if number not in allowed_numbers or allowed_numbers[number] == 0:
            return False
        allowed_numbers[number] -= 1
    return True


def uses_allowed_letters(word, allowed_letters):
    allowed_letters = {x: allowed_letters.count(x) for x in allowed_letters}
    for letter in word:
        if not allowed_letters.get(letter):
            return False
        allowed_letters[letter] -= 1
    return True


class GameCog:

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["number", "n"])
    async def numbers(self, ctx):
        big_numbers = [25, 50, 75, 100]
        small_numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                         1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        allowed_numbers = []
        closest_user = None
        closest_answer = None

        def is_valid_number(message):
            if message.channel != ctx.channel or message.author != ctx.message.author:
                return False
            try:
                number = int(message.content)
                return 0 <= number <= 4
            except ValueError:
                return len(message.content) < 6 and message.content.lower() in ("zero", "one", "two", "three", "four")

        await ctx.send("How many big numbers? Choose a number between 0 and 4.")

        answer = await self.bot.wait_for('message', check=is_valid_number)
        try:
            big_numbers_amount = int(answer.content)
        except ValueError:
            big_numbers_amount = ("zero", "one", "two", "three", "four").index(answer.content.lower())

        for i in range(big_numbers_amount):
            allowed_numbers.append(big_numbers.pop(random.randint(0, len(big_numbers)-1)))

        for i in range(6 - big_numbers_amount):
            allowed_numbers.append(small_numbers.pop(random.randint(0, len(small_numbers)-1)))

        s = "Your numbers are: "
        for i in range(len(allowed_numbers)):
            if i == len(allowed_numbers) - 1:
                s += f"and {allowed_numbers[i]}."
            else:
                s += f"{allowed_numbers[i]}, "

        await ctx.send(s)
        target = random.randint(100, 999)

        def is_valid_answer(message):
            return message.channel == ctx.channel and is_valid_expression(message.content)

        remaining_time = 60.0
        await ctx.send(f"Your target is {target}.")
        question_start = datetime.utcnow()
        while remaining_time > 0:
            try:
                answer = await self.bot.wait_for('message', timeout=remaining_time, check=is_valid_answer)
            except asyncio.TimeoutError:
                remaining_time = -1
                continue
            expression = answer.content
            user = answer.author.display_name

            if uses_allowed_numbers(expression, allowed_numbers):
                try:
                    result = calculate(expression)
                except NotIntegerDivision:
                    await ctx.send(f"No, {user}. Only integer divisions are allowed.")
                except NegativeResult:
                    await ctx.send(f"No, {user}. The result can't be negative at any point")
                except ValueError:
                    await ctx.send(f"No, {user}. That expression is almost valid, but it isn't.")
                else:
                    if result == target:
                        closest_answer = result
                        closest_user = user
                        await ctx.send(f"That's right, {user}")
                        break
                    else:
                        if not closest_answer or result < closest_answer:
                            closest_answer = result
                            closest_user = user
                        await ctx.send(f"That's {result}, {user}, not {target}.")
            else:
                await ctx.send(f"No, {user}. Those numbers aren't allowed.")

            remaining_time = 60 - (datetime.utcnow() - question_start).total_seconds()
        if closest_answer != target:
            if closest_user:
                await ctx.send(f"Time's up! The closest answer was {closest_answer} by {closest_user}!")
            else:
                await ctx.send("Time's up! Nobody even tried!")

    @commands.command(aliases=["letter", "l"])
    async def letters(self, ctx):
        vowels = []
        for vowel, amount in vowels_d.items():
            vowels += [vowel] * amount
        consonants = []
        for consonant, amount in consonants_d.items():
            consonants += [consonant] * amount

        allowed_letters = []
        vowels_amount = 0
        consonants_amount = 0
        closest_answer = None
        closest_user = None

        def is_valid_answer(message):
            return (message.channel == ctx.channel and message.author == ctx.message.author and
                    message.content.lower() in ('c', 'v', 'vowel', 'consonant'))

        await ctx.send("Take a '**c**onsonant' or a '**v**owel'.")

        uppercase_letters = "-"
        for i in range(9):
            if consonants_amount == 6:  # Need at least 3 vowels.
                answer = 'v'
            elif vowels_amount == 5:  # Need at least 4 consonants.
                answer = 'c'
            else:
                answer = await self.bot.wait_for('message', check=is_valid_answer)
                answer = answer.content[0]
            if answer in ('c', 'C'):
                consonants_amount += 1
                new_letter = consonants.pop(random.randint(0, len(consonants)-1))
            else:
                vowels_amount += 1
                new_letter = vowels.pop(random.randint(0, len(vowels)-1))
            allowed_letters.append(new_letter)
            if i == 0:
                uppercase_letters = new_letter.upper()
            else:
                uppercase_letters += f", {new_letter.upper()}"
            await ctx.send(f"The new letter is {new_letter}. Your letters are: {uppercase_letters}")

        def is_valid_answer(message):
            return (message.channel == ctx.channel and message.author == ctx.message.author and
                    letter_re.fullmatch(message.content))
        remaining_time = 60.0
        await ctx.send("Now, try to write the longest possible word using only those letters.")
        question_start = datetime.utcnow()
        while remaining_time > 0:
            try:
                answer = await self.bot.wait_for('message', timeout=remaining_time, check=is_valid_answer)
            except asyncio.TimeoutError:
                remaining_time = -1
                continue
            word = answer.content.lower()
            user = answer.author.display_name

            if uses_allowed_letters(word, allowed_letters):
                if is_valid_word(word):
                    if len(word) == 9:
                        closest_answer = len(word)
                        closest_user = user
                        await ctx.send(f"Woah, {user}, pretty good, you used all letters!")
                        break
                    else:
                        if not closest_answer or len(word) > closest_answer:
                            closest_answer = len(word)
                            closest_user = user
                        await ctx.send(f"{user}, that word has {len(word)} letters, cool!")
                else:
                    await ctx.send(f"Nice try {user}, but that's not a word.")
            else:
                await ctx.send(f"No, {user}. Those letters aren't allowed.")

            remaining_time = 60 - (datetime.utcnow() - question_start).total_seconds()

        if closest_answer != 9:
            if closest_user:
                await ctx.send(f"Time's up! The closest answer word had {closest_answer} letters by {closest_user}!")
            else:
                await ctx.send("Time's up! Nobody even tried!")


def setup(bot):
    bot.add_cog(GameCog(bot))
