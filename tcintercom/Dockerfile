FROM python:3.9.15-slim-bullseye

ADD ./requirements.txt /home/app/requirements.txt
RUN pip install -r /home/app/requirements.txt

ADD ./app /home/root/app
ADD run.py /home/root/run.py

ENV PYTHONUNBUFFERED 1
WORKDIR /home/root
ENTRYPOINT ["./run.py"]
CMD ["auto"]
