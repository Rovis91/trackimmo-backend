# Contributing to TrackImmo

Thank you for considering contributing to TrackImmo! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in the Issues section
2. If not, create a new issue using the bug report template
3. Include detailed steps to reproduce the bug
4. Provide information about your environment

### Suggesting Features

1. Check if the feature has already been suggested in the Issues section
2. If not, create a new issue using the feature request template
3. Describe the feature and its benefits clearly
4. Consider how it would integrate with the existing codebase

### Development Process

1. Fork the repository
2. Create a new branch for your feature or bugfix (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Write or update tests as needed
5. Ensure all tests pass
6. Update documentation if necessary
7. Submit a pull request

### Pull Request Guidelines

- Follow the pull request template
- Reference any related issues
- Update documentation for any new features
- Ensure your code follows the project's style and conventions
- Make sure all tests pass

## Development Setup

1. Clone your forked repository
   ```
   git clone https://github.com/your-username/trackimmo-backend.git
   cd trackimmo-backend
   ```

2. Set up a virtual environment
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Install development dependencies
   ```
   pip install -r requirements-dev.txt  # If applicable
   ```

5. Install Playwright browsers
   ```
   playwright install
   ```

6. Set up your `.env` file
   ```
   cp .env.example .env
   ```

## Testing

Run tests with pytest:
```
pytest
```

## Code Style

This project follows PEP 8 style guidelines with the following additional conventions:

- Use docstrings for all public functions, classes, and methods
- Keep line length to a maximum of 100 characters
- Use type hints where appropriate

## License

By contributing to TrackImmo, you agree that your contributions will be licensed under the project's MIT License. 