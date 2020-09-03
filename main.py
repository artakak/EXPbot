# -*- coding: utf-8 -*-
from telegram import ParseMode, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Updater, CommandHandler, Job, MessageHandler, InlineQueryHandler, Filters, CallbackQueryHandler, ChosenInlineResultHandler
from redmine import Redmine
from jenkinsapi.jenkins import Jenkins
from sqlalchemy_wrapper import SQLAlchemy
import datetime
import time
import telegram
import logging
import sys
import re
import difflib


# Enable logging
logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)

logger = logging.getLogger(__name__)
db = SQLAlchemy('sqlite:///User.db')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), unique=True)
    user_name = db.Column(db.String(200), unique=True)
    user_auth = db.Column(db.Integer, unique=False)

    def __init__(self, user_id, user_name, user_auth):
        self.user_id = user_id
        self.user_name = user_name
        self.user_auth = user_auth

    def __repr__(self):
        return '<User %r, %r>' % (self.user_id, self.user_name)


class EXPbot:

    def __init__(self, telegram):
        self.updater = Updater(telegram)
        self.j = self.updater.job_queue
        self.alert = {}
        self.currissue = {}
        self.curmsg = {}
        self.current_work = {}
        dp = self.updater.dispatcher
        dp.add_handler(CommandHandler('redmine', self.redmine))
        dp.add_handler(CommandHandler('jenkins', self.jenkins))
        dp.add_handler(CommandHandler('auth', self.auth, pass_args=True))
        dp.add_handler(CallbackQueryHandler(self.filter_for_buttons))
        #dp.add_handler(CallbackQueryHandler(self.filter_for_inline))
        #dp.add_handler(InlineQueryHandler(self.inline_search))
        #dp.add_handler(ChosenInlineResultHandler(self.inline_picture))
        #dp.add_handler(MessageHandler([Filters.text], self.command_filter))
        #dp.add_handler(MessageHandler([Filters.command], self.unknow))

    def logger_wrap(self, message, command):
        user = message.from_user
        logger.info(u'%s from %s @%s %s' % (message.text[0:20],
                                            user.first_name,
                                            user.username,
                                            user.last_name))

    @staticmethod
    def put_user(user, key, value):
        user.__setattr__(key, value)
        db.session.commit()

    def auth(self, bot, update, args):
        user = db.query(User).filter_by(user_id=str(update.message.from_user.id)).first()
        if user.user_auth == 1:
            return True
        elif args == ['123']:
            EXPbot.put_user(user, 'user_auth', 1)
            bot.sendMessage(update.message.chat_id, text='Ok', parse_mode=ParseMode.MARKDOWN)
            return True
        else:
            bot.sendMessage(update.message.chat_id, text=u'Необходима авторизация', parse_mode=ParseMode.MARKDOWN)
            return False

    def redmine(self, bot, update):
        try:
            db.add(User(str(update.message.from_user.id), update.message.from_user.name, 0))
            db.commit()
        except:
            db.rollback()
        self.logger_wrap(update.message, 'redmine')
        self.alert[str(update.message.from_user.id)] = 0
        if not self.auth(bot, update, args=None):
            return
        chat_id = str(update.message.chat_id)
        try:
            bot.editMessageReplyMarkup(chat_id=chat_id, message_id=self.curmsg)
        except: pass
        text = EXPbot.redmine_info()
        self.currissue[str(update.message.from_user.id)] = text
        keyboard = EXPbot.do_keyboard('redmine')
        bot.sendMessage(chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    @staticmethod
    def redmine_info():
        t_time = datetime.date.today()
        redmine = Redmine('http://help.heliosoft.ru', key='')
        issues_open_prov = redmine.issue.filter(project_id='experium', status_id='3', cf_19='me')
        issues_open_me = redmine.issue.filter(assigned_to_id='me')
        issues_open_all_totay = redmine.issue.filter(project_id='experium', created_on=str(t_time))
        issues_open_all_totay_up = redmine.issue.filter(project_id='experium', updated_on=str(t_time))
        text = ''
        text += u'*НА ПРОВЕРКУ!!!*\n'
        for t in issues_open_prov:
            text += (u'[%s](http://help.heliosoft.ru/issues/%s) %s %s\n' % (str(t.id), str(t.id), str(t.status), str(t).decode('utf8')))
        text += u'*\n\nЗАДАЧИ НА МНЕ!!!*\n'
        for t in issues_open_me:
            text += (u'[%s](http://help.heliosoft.ru/issues/%s) %s %s\n' % (str(t.id), str(t.id), str(t.status), str(t).decode('utf8')))
        text += (u'\n\n*Тикеты, добавленные за %s:*\n' % str(t_time.strftime('%d %b %Y')))
        for t in issues_open_all_totay:
            text += (u'[%s](http://help.heliosoft.ru/issues/%s) %s %s\n' % (str(t.id), str(t.id), str(t.status), str(t).decode('utf8')))
        text += (u'\n\n*Тикеты, обновленные за %s:*\n' % str(t_time.strftime('%d %b %Y')))
        for t in issues_open_all_totay_up:
            text += (u'[%s](http://help.heliosoft.ru/issues/%s) %s %s\n' % (str(t.id), str(t.id), str(t.status), str(t).decode('utf8')))
        return text

    def jenkins(self, bot, update):
        try:
            db.add(User(str(update.message.from_user.id), update.message.from_user.name, 0))
            db.commit()
        except:
            db.rollback()
        try:
            chat_id = str(update.message.chat_id)
            if not self.auth(bot, update, args=None):
                return
            try:
                bot.editMessageReplyMarkup(chat_id=chat_id, message_id=self.curmsg)
            except: pass
            self.curmsg[str(update.message.from_user.id)] = str(update.message.message_id + 1)
            callback = 0
        except:
            chat_id = str(update.callback_query.message.chat_id)
            self.curmsg[str(update.callback_query.from_user.id)] = update.callback_query.message.message_id
            callback = 1
        self.J = Jenkins('http://buildsrv.experium.ru/', username="", password="")
        text = u'*Список доступных работ:*\n'
        buttons = []
        for t in self.J.keys():
            if 'Experium' in t:
                buttons.append([telegram.InlineKeyboardButton(text=str(t), callback_data=str(t))])
        keyboard = telegram.InlineKeyboardMarkup(buttons)
        if callback == 0:
            bot.sendMessage(chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        else:
            bot.editMessageText(text=text, chat_id=chat_id, message_id=self.curmsg[str(update.callback_query.from_user.id)],
                                parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    def jenkins_work_info(self, cur_job):
        text = ''
        j = self.J.get_job(cur_job)
        try:
            q = j.get_last_good_build()
            text = u'*%s*\n\n*Последняя удачная сборка:*\n%s SVN REV - %s' % (cur_job, str(q), str(q._get_svn_rev()))
            changes = q.get_changeset_items()
            text += u'\n\n*Изменения:*'
            for t in range(len(changes)):
                text += re.sub(r'#?(\d{4,}\b)', r'[#\1](http://help.heliosoft.ru/issues/\1)', u'\n*%s)*%s' % (str(t + 1), str(changes[t]['msg']).decode('utf8')))
        except: pass
        if j.is_running():
            text += u'\n\n*Текущее состояние:* идет сборка'
        else:
            text += u'\n\n*Текущее состояние:* сборка не выполняется'
        return text

    def filter_for_buttons(self, bot, update):
        query = update.callback_query
        if query.data == 'jenkins_build':
            j = self.J.get_job(self.current_work[str(query.from_user.id)])
            if not j.is_queued_or_running():
                self.J.build_job(self.current_work[str(query.from_user.id)])
            self.job_jenkins_build = Job(self.build_monitor, 10.0, repeat=True, context=[query.message.chat_id, self.current_work[str(query.from_user.id)]])
            self.j.put(self.job_jenkins_build)
            bot.answerCallbackQuery(callback_query_id=str(query.id), text=u'Сборка запущена')
        elif query.data == 'jenkins_close':
            self.jenkins(bot, update)
        elif query.data == 'redmine_alert':
            if self.alert[str(query.from_user.id)] == 0:
                bot.answerCallbackQuery(callback_query_id=str(query.id), text=u'Уведомления включены')
                self.alert[str(query.from_user.id)] = 1
                self.job_redmine_alert = Job(self.issue_monitor, 60.0, repeat=True, context=[query.message.chat_id, query.from_user.id])
                self.j.put(self.job_redmine_alert)
            else:
                bot.answerCallbackQuery(callback_query_id=str(query.id), text=u'Уведомления выключены')
                self.alert[str(query.from_user.id)] = 0
        else:
            text = self.jenkins_work_info(query.data)
            self.current_work[str(query.from_user.id)] = query.data
            keyboard = EXPbot.do_keyboard('jenkins')
            bot.editMessageText(text=text, chat_id=query.message.chat_id, message_id=self.curmsg[str(query.from_user.id)],
                                parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    @staticmethod
    def do_keyboard(flag):
        if flag == 'jenkins':
            keyboard = telegram.InlineKeyboardMarkup([[telegram.InlineKeyboardButton(text=u'⚒', callback_data='jenkins_build'),
                                                       #telegram.InlineKeyboardButton(text=u'📢', callback_data='jenkins_update'),
                                                       telegram.InlineKeyboardButton(text=u'❌', callback_data='jenkins_close')]])
        if flag == 'redmine':
            keyboard = telegram.InlineKeyboardMarkup([[telegram.InlineKeyboardButton(text=u'📢', callback_data='redmine_alert')]])
        return keyboard

    def build_monitor(self, bot, job):
        j = self.J.get_job(job.context[1])
        if j.is_running():
            return
        else:
            bot.sendMessage(chat_id=job.context[0], text=u'Сборка %s завершена\n\n%s' % (job.context[1], self.jenkins_work_info(job.context[1])),
                            parse_mode=ParseMode.MARKDOWN)
            self.job_jenkins_build.schedule_removal()

    def issue_monitor(self, bot, job):
        if self.alert[str(job.context[1])] == 1:
            try:
                new_text = EXPbot.redmine_info()
                if self.currissue[str(job.context[1])] != new_text:
                    cd = difflib.ndiff(u''.join(self.currissue[str(job.context[1])]).splitlines(), u''.join(new_text).splitlines())
                    final = '\n'.join(list(cd))
                    bot.sendMessage(chat_id=job.context[0], text=u'📢\n%s' % final,
                                    parse_mode=ParseMode.MARKDOWN)
                    self.currissue[str(job.context[1])] = new_text
            except:
                pass
        else:
            self.job_redmine_alert.schedule_removal()

    def unknow(self, bot, update):
        self.logger_wrap(update.message, 'unknow')

    def error(self, bot, update, error):
        self.logger_wrap(update.message, 'error')
        logger.warn('Update "%s" caused error "%s"' % (update, error))

    def idle(self):
        self.updater.start_polling()
        self.updater.idle()


def main():
    try:
        bot_token = '281794038:AAGuEkrtwq1DKsdMCnaAi_FiCA9wn2EqOas'
        #botan_token = 'QMnB3zioDRi_qDSM:dKln:BpVXgHcH-A'
        #146.185.181.222:22

    except Exception as e:
        logger.exception(e)
        sys.exit()

    if not bot_token:
        logger.error('Bot token is empty')
        sys.exit()

    db.create_all()
    bot = EXPbot(bot_token)
    bot.idle()


if __name__ == '__main__':
    main()
