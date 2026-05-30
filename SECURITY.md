# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this library, please report it by emailing **hello@zzinnovate.com**. Include a clear description of the issue and steps to reproduce if possible.

We will review and respond to security reports promptly.

## Best Practices for Users

When using lettermint-django, follow these security guidelines:

### Protect Your API Keys

- **Never commit API keys** to version control or include them in your source code
- **Use environment variables** to store your Lettermint API key
- **Limit API key permissions** to only what your application needs in the Lettermint dashboard

### Keep Dependencies Updated

We recommend always using the latest version to receive security patches:

```bash
pip install --upgrade lettermint-django
```

### Example: Secure API Key Usage

```python
import os

# Good: Load from environment variable
LETTERMINT_API_KEY = os.getenv('LETTERMINT_API_KEY')

# Bad: Hard-coded API key (never do this!)
# LETTERMINT_API_KEY = 'lm_your_secret_key_here'
```

## Supported Versions

We recommend always using the latest version. Security updates will be released as patch versions.
