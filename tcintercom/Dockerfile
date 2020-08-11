FROM python:3.8-slim

ADD ./requirements.txt /home/app/requirements.txt
RUN pip install -r /home/app/requirements.txt

ENV PYTHONUNBUFFERED 1
WORKDIR /home/tcintercom
CMD python tcintercom/main.py
