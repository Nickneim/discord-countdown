import random
import asyncio
from discord.ext import commands
from datetime import datetime
import re

parentheses_re = re.compile(r'\(([-+*xX/ \d]+)\)')
multiplication_division_re = re.compile(r'(\d+) *([*xX/]) *(\d+)')
addition_subtraction_re = re.compile(r'(\d+) *([-+]) *(\d+)')
expression_start_re = re.compile(r'[( ]*\d')
expression_simple_re = re.compile(r'^[-+*xX/ ()\d]+$')
number_re = re.compile(r'\d+')
repeated_operator_re = re.compile(r'[-+*xX/]\D*[-+*xX/]')


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
    if not expression_start_re.match(expression):
        return False
    if not expression_simple_re.match(expression):
        return False
    if repeated_operator_re.search(expression):
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


def uses_allowed_numbers(expression, allowed_numbers):
    allowed_numbers = {x: allowed_numbers.count(x) for x in allowed_numbers}
    for number in number_re.finditer(expression):
        number = int(number.group(0))
        if number not in allowed_numbers:
            return False
        if allowed_numbers[number] == 0:
            return False
        allowed_numbers[number] -= 1
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

        def is_valid_number(message):
            if message.channel != ctx.channel or message.author != ctx.message.author:
                return False
            try:
                number = int(message.content)
                return 0 <= number <= 4
            except ValueError:
                return len(message.content) < 6 and message.content.lower() in ("zero", "one", "two", "three", "four")

        await ctx.send("How many big numbers?")

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

            if uses_allowed_numbers(expression, allowed_numbers):
                try:
                    result = calculate(expression)
                except NotIntegerDivision:
                    await ctx.send(f"No, {answer.author.display_name}. Only integer divisions are allowed.")
                except NegativeResult:
                    await ctx.send(f"No, {answer.author.display_name}. The result can't be negative at any point")
                except ValueError:
                    await ctx.send(f"No, {answer.author.display_name}. That expression is almost valid, but it isn't.")
                else:
                    if result == target:
                        await ctx.send(f"That's right, {answer.author.display_name}")
                        break
                    else:
                        await ctx.send(f"That's {result}, {answer.author.display_name}, not {target}.")
            else:
                await ctx.send(f"No, {answer.author.display_name}. Those numbers aren't allowed.")

            remaining_time = 60 - (datetime.utcnow() - question_start).total_seconds()
        if remaining_time <= 0:
            await ctx.send(f"Time's up! The answer was {target} lol")


def setup(bot):
    bot.add_cog(GameCog(bot))
