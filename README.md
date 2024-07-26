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


### Receiving webhooks from Intercom
To actually start receiving webhooks from intercom, there are two steps that need to be done. The first is to call
ngrok for the port that the web app is running on, for example:

```bash
ngrok http 8000
```

For the second step, you will need to head over to the intercom developer hub and either set up a new app, or use an
old one that is already there, making sure the workspace for either option is `TutorCruncher [TEST]`. Then click on 
the app, and on the left hand side click on 'Webhooks'. From there you should see in the top right, a button that says
`Edit` which allows you to change the `Endpoint URL`, set this endpoint url to your ngrok url ending with /callback/ 
and click save. An example endpoint url could be: `http://1234abcd.ngrok-free.app/callback/`.

To confirm that everything is set up correctly, you can click the `Send a test request` button, and you should see a
response in the ngrok terminal and the terminal that the web app is running on.

You can select which webhooks this app will send out at the bottom of the page. These topics are all the different
webhooks that can be sent.

### Setting up TutorCruncher
Optionally you can set up TutorCruncher. All you need to do is in your `_localsettings.py` file, add the 
`IC_SECRET_TOKEN` and the `IC_CLIENT_SECRET`. The `IC_CLIENT_SECRET` token can be found on the `Basic information` tab
on your app in the developer hub, look out for `Client secret`, and the `IC_SECRET_TOKEN` is the token found under 
the `Authentication` tab which will be under the `Access token` section.
