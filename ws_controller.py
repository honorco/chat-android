import time

from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import ThreeLineListItem, OneLineListItem
from kivymd.uix.button import Button as MDButton
from client_connector import ClientConnector
import json
import os

# здесь реализованны методы работы и обработки сообщений по вебсокету
class WSConstroller:
    URL = 'musaev.online'
    PORT = 8765

    _id_instance_button = dict()
    object_chats = None
    _id_button = list()

    connector = None
    db = None

    def __init__(self, db): # инициирует подлючения, создает веб-сокет соединение, прослушивает роут на получение сообщения
        self.connector = ClientConnector(self.URL, self.PORT,
                                         {'/messages/create': lambda connection, data: self.get_message_from_server(
                                             data)}, db)
        self.db = db

    def synchronization_messages(self, db, data): # синхронизирует сообщения ( вызывается в synchronization_chats)
        for message in data:
            db.set_message(message[0], message[1], message[3], author=message[2])

    def synchronization_chats(self, db, data, connector, object_main_window, list_settings): # синхронизирует чаты ( вызывается в synch_all)
        correct_format_db = list()
        for tpl in db.get_chats():
            correct_format_db.append([tpl[2], tpl[1]])
        self.synch_ui_clear_buttons(object_main_window)
        if correct_format_db != data:
            username = db.get_username()
            os.remove(db.get_path_db())
            db.create_db()
            db.set_username(username)
            for chat in data:
                db.set_chats(chat[1], chat[0])
                connector.send('/messages/get', message=json.dumps({'chat_id': chat[0]}),
                               callback=lambda connection, data_server: self.synchronization_messages(db, json.loads(
                                   data_server)))
                self.synch_ui_add_buttons(object_main_window, chat, list_settings)
        else:
            for chat in db.get_chats():
                self.synch_ui_add_buttons(object_main_window, chat, list_settings)

    # Синхронизирует все чаты и сообщения (вызывается в начале запуска приложения) в случае отсутствия интернета ожидает в отдельном потоке
    def synch_all(self, object_main_window, list_settings):
        while not self.connector.network_status:
            time.sleep(1)
        self.connector.send('/chats/get',
                            callback=lambda connection, data_server: self.synchronization_chats(self.db,
                                                                                                json.loads(
                                                                                                    data_server),
                                                                                                self.connector,
                                                                                                object_main_window,
                                                                                                list_settings))

    def synch_messages(self): # синхронизирует сообщения в момент входа в чат
        if self.connector.network_status:
            self.connector.send('/messages/get', message=json.dumps({'chat_id': self._id_button[0]}),
                                callback=lambda connection, data_server: self.write_messages(json.loads(
                                    data_server)))
        else:
            dialog = None
            if not dialog:
                dialog = MDDialog(text='Connection fail!')
            dialog.open()

    def write_messages(self, data): # отображает сообщения в ui
        if not data:
            self.object_chats.parent.ids.chat.ids.messages.clear_widgets()
            return
        correct_format_db = list()
        for i in range(len(data)):
            data[i].pop(4)
            data[i].pop(3)
        for tpl in self.db.get_messages(self._id_button[0]):
            correct_format_db.append(list(tpl))
        if correct_format_db != data:
            self.db.delete_messages(self._id_button[0])
            self.object_chats.parent.ids.chat.ids.messages.clear_widgets()
            for message in data:
                self.db.set_message(message[0], message[1], self._id_button[0], message[2])
                item_mes = ThreeLineListItem(text=message[0], secondary_text=message[2],
                                             tertiary_text=message[1])
                self.object_chats.parent.ids.chat.ids.messages.add_widget(item_mes)

    def insert_local_db(self, response, text_input, username, date_sent, chat_id, object_dialog): # записывает сообдения в локальное бд
        if response['status'] == 'ok':
            self.db.set_message(text_message=text_input, time=date_sent, chat_id=chat_id, author=username)
            item_mes = ThreeLineListItem(text=text_input, secondary_text=username,
                                         tertiary_text=date_sent)
            object_dialog.parent.ids.chat.ids.messages.add_widget(item_mes)
        elif response['status'] == 'fail':
            item_mes = OneLineListItem(text='Error! The message was not delivered!')
            object_dialog.parent.ids.chat.ids.messages.add_widget(item_mes)

    def send_message(self, text_message, time, author, chat_id, object_dialog): # отравляет сообщения на сервер
        if self.connector.network_status:
            self.connector.send('/messages/create', message=json.dumps(
                {'text_message': text_message, 'time': time, 'author': author, 'chat_id': chat_id}),
                                callback=lambda connection, response: self.insert_local_db(json.loads(response),
                                                                                           text_message, author, time,
                                                                                           chat_id, object_dialog))
        else:
            item_mes = OneLineListItem(text='Error! No Internet connection!')
            object_dialog.parent.ids.chat.ids.messages.add_widget(item_mes)

    def synch_ui_clear_buttons(self, object_main_window): # удаляет в ui кнопки чата
        object_main_window.parent.ids.main_window.ids.chats.clear_widgets()

    def synch_ui_add_buttons(self, object_main_window, chat, list_settings):  # добавляет в ui кнопки чата
        btn = MDButton(text=chat[1], font_size=50, bold=True,
                       on_press=lambda x: object_main_window.parent.ids.main_window.go_to_chat(instance=x,
                                                                                               ref_id_button=
                                                                                               list_settings[0]),
                       size_hint_y=None, height=list_settings[1].standard_increment * 1.5,
                       background_color=(0, 0.749, 1, 0.5))
        self._id_instance_button[chat[0]] = btn
        object_main_window.parent.ids.main_window.ids.chats.add_widget(btn)

    def get_message_from_server(self, response): # инициируется в момент получения сообщения, отображает новое сообщение в диалоге
        self.db.set_message(text_message=response['text_message'], time=response['time'], chat_id=response['chat_id'],
                            author=response['author'])
        if self.object_chats.parent.current == 'Chat' and self._id_button[0] == response['chat_id']:
            item_mes = ThreeLineListItem(text=response['text_message'], secondary_text=response['author'],
                                         tertiary_text=response['time'])
            self.object_chats.parent.ids.chat.ids.messages.add_widget(item_mes)

    def set_id_button(self, _id_button):
        self._id_button = _id_button

    def set_object_chats(self, object_chats, _id_button):
        self.object_chats = object_chats
        self._id_button = _id_button
        self.connector.set_object_chats(object_chats, _id_button)

    def get_id_instance_buttons(self):
        return self._id_instance_button
