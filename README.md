# TC Intercom

A simple web app built with FastAPI to deal with Intercom webhooks; and has a job that runs periodically that handles 
and updates intercom duplicates.

### Running the web app
To run the web app, you can call either of the following commands:

```bash
make web
```

OR

```bash
python tcintercom/run.py auto
```

### Running jobs
On Render, we have CRON jobs setup which run every so often. These jobs take a command to run, for example

```bash
python tcintercom/app/cron_job.py 
```

### Setting up keys locally

To set up keys locally, you'll need to head over to the 
[intercom developer hub](https://app.intercom.com/a/apps/u6r3i73k/developer-hub) and either set up a new app or use
an existing one, making sure the workspace for either option is `TutorCruncher [TEST]`.

Then click on the app (either the one you've chosen or the one you created), and now we need to set up a `.env` file to 
store the environment variables. Create this file in the TCIntercom directory. The secrets you'll need to start off are 
the `ic_secret_token` and `ic_client_secret`. Later any other environment variables can be added such as your 
`logfire_token` etc. You can get the `ic_secret_token` by heading over to the `Authentication` tab and copying the 
`Access token`. The `ic_client_secret` can be found under the `Basic information` tab, and you'll want the key 
labelled `Client secret`.

### Receiving webhooks from Intercom
To actually start receiving webhooks from intercom, there are two steps that need to be done. The first is to call
ngrok for the port that the web app is running on, for example:

```bash
ngrok http 8000
```

Now that we've done that, head over to the 'Webhooks' tab on the intercom app. From there you should see in the top 
right, a button that says `Edit` which allows you to change the `Endpoint URL`, set this endpoint url to your ngrok 
url ending with /callback/ and click save. An example endpoint url could be: 
`http://1234abcd.ngrok-free.app/callback/`.

To confirm that everything is set up correctly, you can click the `Send a test request` button, and you should see a
response in the ngrok terminal and the terminal that the web app is running on.

You can select which webhooks this app will send out at the bottom of the page. These topics are all the different
webhooks that can be sent. You can add the ones you want to receive by clicking `Edit` in the top right of the page and
then scrolling down to the dropdown and selecting the ones you want. Currently at the time of writing, the only webhook
we handle is `conversation.contact.created`, the others we process and log a `No action required`.

### Setting up TutorCruncher
Optionally you can set up TutorCruncher. All you need to do is in your `_localsettings.py` file, add the 
`IC_SECRET_TOKEN` and the `IC_CLIENT_SECRET`. The `IC_CLIENT_SECRET` token can be found on the `Basic information` tab
on your app in the developer hub, look out for `Client secret`, and the `IC_SECRET_TOKEN` is the token found under 
the `Authentication` tab which will be under the `Access token` section.

Then all you need to do is log in and switch to the live branch, head over to Support > Tickets and click `Open a new
ticket`. Once you submit your ticket, you should see a ticket opened on the `Intercom [TEST]` workspace, a webhook
for a conversation created should be sent to the web app, and if you have logfire running, the logs sent over logire.
