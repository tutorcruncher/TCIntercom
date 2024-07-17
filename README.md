# TC Intercom

A simple web app built with FastAPI to deal with Intercom webhooks.

### Running the web app
To run the web app, you first need to export the environment variable 'DYNO' to something that starts with 'web', 
for example:

```bash
export DYNO=web123
```

Then you can call the following command to run the web app:

```bash
python tc_intercom/run.py auto
```

### Running the worker
To run the worker, we don't need to set an environment variable and can just call the following command:

```bash
python tc_intercom/run.py auto
```
