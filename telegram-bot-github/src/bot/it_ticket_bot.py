# it_ticket_bot.py
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from src.dialog.bot_dialog import BotDialog, States
from src.data.form_data import FormData
from src.services.email_service import EmailService

class ITTicketBot:
    def __init__(self, token, smtp_server, smtp_port, email_sender, email_password, email_recipient):
        self.token = token
        self.email_service = EmailService(smtp_server, smtp_port, email_sender, email_password, email_recipient)
        self.form_data = FormData()
        self.dialog = BotDialog(self.form_data, self.email_service)
        self.application = Application.builder().token(self.token).build()

    def setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.dialog.start)],
            states={
                States.SUBJECT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_subject)],
                States.OTHER_SUBJECT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_other_subject)],
                States.NAME.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_name)],
                States.DEPARTMENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_department)],
                States.OTHER_DEPARTMENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_other_department)],
                States.CAMPUS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND | filters.LOCATION, self.dialog.get_campus)],
                States.OTHER_CAMPUS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_other_campus)],
                States.BUILDING.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_building)],
                States.FLOOR.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_floor)],
                States.ROOM.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_room)],
                States.PHONE.value: [MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, self.dialog.get_phone)],
                States.EMAIL.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_email)],
                States.DESCRIPTION.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_description)],
                States.CALLBACK.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.get_callback)],
            },
            fallbacks=[CommandHandler('cancel', self.dialog.cancel)]
        )
        self.application.add_handler(conv_handler)

    def run(self):
        self.setup_handlers()
        self.application.run_polling()