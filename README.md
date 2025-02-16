# Split Shark - Telegram Expense Tracker Bot

Split Shark is a Telegram bot designed to help groups track shared expenses and calculate balances effortlessly. Whether you're splitting bills with friends, roommates, or colleagues, Split Shark makes it easy to keep track of who owes what. With its ability to convert between currencies, Split Shark is your ideal travel expense assistant, leaving you to enjoy your travels to the fullest!

## Features

**Set Group Currency**: Define the currency for your group using `/setcurrency`.

**Add Expenses**: Record expenses with details like the payer, amount, and involved members using `/add_expense`.

**Calculate Balances**: View who owes whom and the total expenditures using `/calculate_balances`.

**Currency Conversion**: Convert balances to another currency using `/exchangebal <target_currency>`.

**User-Friendly Interface**: Interactive buttons and clear messages for seamless usage.

## How to Use

1. Add the Bot to Your Group:
2. Search for @split_shark_bot on Telegram and add it to your group. *Note: Add @split_shark_bot and **ALL** members as administrators*
3. Set the Group Currency: Use the `/setcurrency <currency_symbol>` command to set the currency for your group (e.g., `/setcurrency SGD`).
4. Add Expenses: Use the `/add_expense` command to record a new expense. The bot will guide you through the process:
5. Enter the expense name.
6. Select the payer.
7. Enter the amount.
8. Select the involved members.
9. Calculate Balances: Use the `/calculate_balances` command to view the current balances and who owes whom.
10. Convert Balances to Another Currency: Use the `/exchangebal <target_currency>` command to view balances in a different currency (e.g., `/exchangebal EUR`).

## Acknowledgements
- Thanks to the [python-telegram-bot](https://python-telegram-bot.org/) library for making Telegram bot development easy.
- Thanks to [FreeCurrencyAPI](https://freecurrencyapi.com/docs/#official-libraries) for providing currency exchange rates.
- Thanks to Google Lab's [ImageFX](https://labs.google/fx/tools/image-fx) for generating Split Shark's display photo

## Contact
If you have any questions or feedback, feel free to reach out:
- Email: wentingchua@gmail.com
- Telegram: @went1ng

### Enjoy using Split Shark! 🦈

