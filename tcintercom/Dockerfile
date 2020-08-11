FROM python:3.8-slim

ADD ./requirements.txt /home/app/requirements.txt
RUN pip install -r /home/app/requirements.txt

ADD ./main.py /home/tcintercom/main.py

ENV PYTHONUNBUFFERED 1
WORKDIR /home/tcintercom
CMD python main.py
