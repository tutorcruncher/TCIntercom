# TC Intercom

TutorCruncher's service for managing Intercom. Handles webhooks from Intercom (e.g., conversation events, blog subscriptions) and runs a periodic cron job to identify and mark duplicate contacts.

## Running Locally

1. Install dependencies:
   ```bash
   make install-dev
   ```

2. Create a `.env` file with your Intercom credentials:
   ```
   ic_secret_token=<your-access-token>
   ic_client_secret=<your-client-secret>
   ```

3. Start the web server:
   ```bash
   make web
   ```

The app will be available at `http://localhost:8000`.

## Testing

Run the test suite:
```bash
make test
```

Run tests with coverage:
```bash
make test-cov
```
