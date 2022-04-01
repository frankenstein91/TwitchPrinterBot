#!/bin/env python3
import inspect
import logging
import argparse
import signal

from socket import socket
from time import sleep
from sqlalchemy import *
from sqlalchemy.orm import *
from sqlalchemy.ext.declarative import declarative_base

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

Base = declarative_base()
Session = sessionmaker()

# user table
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))

    def __repr__(self):
        return "<User(name='%s', email='%s', password='%s')>" % (
            self.name,
            self.email,
            self.password,
        )


# message table
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String(500))
    printed = Column(Boolean, default=False)
    blocked = Column(Boolean, default=False)

    def __repr__(self):
        return "<Message(user_id='%s', message='%s')>" % (self.user_id, self.message)


# badword table
class Badword(Base):
    __tablename__ = "badwords"
    id = Column(Integer, primary_key=True)
    word = Column(String(50))

    def __repr__(self):
        return "<Badword(word='%s')>" % (self.word)


# statistics table
class Statistic(Base):
    __tablename__ = "statistics"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    value = Column(Integer)

    def __repr__(self):
        return "<Statistic(name='%s', value='%s')>" % (self.name, self.value)


def signal_handler(signal, frame):
    logging.info("You pressed Ctrl+C!")
    logging.info("will stop as soon as possible")
    global interrupted
    interrupted = True


#render text to a black and white bmp
def BitmapFromText(text, font, height, width=400):
    img = PIL.Image.new("1", (width, height), "white")
    draw = PIL.ImageDraw.Draw(img)
    draw.text((0, 0), text, font=font, fill="black")
    return img


signal.signal(signal.SIGINT, signal_handler)
interrupted = False

if __name__ == "__main__":
    # parse arguments
    parser = argparse.ArgumentParser(
        description="A twitch bot that prints messages from a channel to a cat printer",
        prog="bot.py",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=50),
    )
    parser.add_argument(
        "-l",
        "--log",
        help="log level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument(
        "-t", "--tigger", help="tigger word for printing (after !)", default="print"
    )
    # get SQLAlchemy connection string
    parser.add_argument(
        "-c",
        "--connection",
        help="SQLAlchemy connection string",
        default="sqlite:///PrintBot.db",
    )
    # make a arg group for the twitch.tv para
    group = parser.add_argument_group("Twitch.tv")
    group.add_argument(
        "-u", "--username", help="Twitch.tv username", required=True, type=str
    )
    group.add_argument("-T", "--token", help="Twitch.tv token", required=True, type=str)
    group.add_argument(
        "--ircchannel", help="IRC channel to join", required=True, type=str
    )
    group.add_argument("--ircserver", help="IRC server", default="irc.chat.twitch.tv")
    group.add_argument("--ircport", help="IRC port", default=6667)
    # make a arg group for the printer para
    group = parser.add_argument_group("🐱Printer")
    group.add_argument("-D", "--devidename", help="BLE Device name", type=str, default="GT01")
    args = parser.parse_args()
    # set up logging
    logging.basicConfig(
        level=args.log.upper(), format="%(asctime)s %(levelname)s %(message)s"
    )
    # set up SQLAlchemy
    logging.info(f"Connecting to {args.connection}")
    logging.debug(f"try to create engine with {args.connection}")
    try:
        engine = create_engine(args.connection)
    except Exception as e:
        logging.error(f"failed to create engine with {args.connection}")
        logging.error(e)
        exit(1)
    Session.configure(bind=engine)
    # create tables if not exist
    logging.info("create tables if not exist")
    logging.debug("try to create tables")
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception as e:
        logging.error("failed to create tables")
        logging.error(e)
        exit(1)
    # connect to twitch.tv
    logging.info("connect to twitch.tv")
    logging.debug(
        f"try to connect to ircserver {args.ircserver}:{args.ircport} with username {args.username} on channel {args.ircchannel}"
    )
    try:
        sock = socket()
        sock.connect((args.ircserver, args.ircport))
        sock.send(f"PASS {args.token}\r\n".encode())
        sock.send(f"NICK {args.username}\r\n".encode())
        sock.send(f"JOIN #{args.ircchannel}\r\n".encode())
    except Exception as e:
        logging.error("failed to connect to twitch.tv")
        logging.error(e)
        exit(1)
    # listen to twitch.tv chat
    logging.info("listen to twitch.tv chat")
    while True:
        if interrupted:
            logging.info("will close all connections")
            sock.close()
            break
        try:
            data = sock.recv(2048).decode() # receive data from twitch.tv
        except Exception as e:
            logging.error("failed to receive data from twitch.tv")
            logging.error(e)
            continue
        if len(data) > 0:
            for line in data.splitlines():
                logging.debug(f"received data from twitch.tv: {line}")
                if line.startswith("PING"):
                    sock.send(f"PONG {line.split()[1]}\r\n".encode())
                    logging.debug(f"answer to twitch.tv ping: {line.split()[1]}")

