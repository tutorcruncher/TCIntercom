FROM python:3.8-slim

ADD ./requirements.txt /home/root/requirements.txt
RUN pip install -r /home/root/requirements.txt

ADD ./main.py /home/root/main.py

ENV PYTHONUNBUFFERED 1
WORKDIR /home/root
CMD python main.py
