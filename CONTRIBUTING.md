# Contributing to KemonoDownloader

Thank you for your interest in contributing to KemonoDownloader! We welcome contributions from the community to help improve this tool for downloading content from Kemono.su. Whether you’re fixing bugs, adding features, or improving documentation, your efforts are greatly appreciated.

## Community Guidelines
To maintain a safe and productive environment, please adhere to the following rules:
- **No Spam or Unverified Links**: Do not post links to unverified or external tools, as they may pose security risks. Such actions will be considered spam and may lead to removal of comments or restrictions on your contributions.
- **Provide Constructive Feedback**: When reporting issues, include detailed information, reproducible steps, or code samples. Avoid vague or promotional content.
- **Respect the Community**: Be respectful in all interactions.

Violations of these guidelines may result in warnings, removal of comments, temporary or permanent bans from contributing, or reporting to GitHub for further action.

## How to Contribute

### 1. Follow the Code of Conduct
All contributors are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it to understand the standards we expect from our community, including respecting intellectual property rights and refraining from illegal activities.

### 2. Check Existing Issues and Discussions
Before starting work, check the [Issues page](https://github.com/VoxDroid/KemonoDownloader/issues) and [Discussions tab](https://github.com/VoxDroid/KemonoDownloader/discussions) to see if your idea or bug has already been reported. If not, feel free to open a new issue or start a discussion to propose your contribution.

### 3. Fork and Clone the Repository
1. Fork the repository by clicking the "Fork" button on the [KemonoDownloader GitHub page](https://github.com/VoxDroid/KemonoDownloader).
2. Clone your fork to your local machine:
   ```bash
   git clone https://github.com/YOUR_USERNAME/KemonoDownloader.git
   cd KemonoDownloader
   ```

### 4. Create a Branch
Create a new branch for your changes. Use a descriptive name that reflects the purpose of your contribution:
```bash
git checkout -b feature/add-new-feature
# or
git checkout -b fix/bug-description
```

### 5. Set Up Your Development Environment
1. Ensure you have **Python 3.9+** installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install [Briefcase](https://briefcase.readthedocs.io/) for building the app:
   ```bash
   pip install briefcase
   ```
4. Test the app locally to ensure it runs:
   ```bash
   briefcase run
   ```

### 6. Make Your Changes
- Write clean, readable code following Python best practices (e.g., PEP 8 for style).
- If adding a new feature, ensure it aligns with the project’s goals (e.g., enhancing download functionality, improving the UI, or adding support for new file types).
- If fixing a bug, include a clear description of the issue and how your changes address it.
- Update documentation (e.g., `README.md`, in-app Help tab) if your changes affect usage or installation.

### 7. Test Your Changes
- Test your changes thoroughly on your local machine across supported platforms (Windows, macOS, Linux) if possible.
- Ensure the app still works as expected (e.g., downloading posts, archiving creators, UI functionality).
- Verify that your changes don’t break existing features or introduce new bugs.

### 8. Commit Your Changes
Write clear, concise commit messages that describe your changes:
```bash
git add .
git commit -m "Add feature: support for new file type XYZ"
# or
git commit -m "Fix bug: resolve crash when downloading empty posts"
```

### 9. Push and Submit a Pull Request
1. Push your branch to your fork:
   ```bash
   git push origin feature/add-new-feature
   ```
2. Go to the [KemonoDownloader GitHub page](https://github.com/VoxDroid/KemonoDownloader) and click "New Pull Request."
3. Select your branch and submit the pull request with a detailed description of your changes, including:
   - What you changed and why.
   - Any issues your changes address (e.g., link to an issue number).
   - Screenshots or logs, if applicable (e.g., for UI changes).

### 10. Respond to Feedback
The maintainers will review your pull request and may request changes or provide feedback. Be responsive and make any necessary updates to your branch. Once approved, your changes will be merged into the main branch.

## Coding Standards
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code style (e.g., 4-space indentation, 79-character line length).
- Use descriptive variable and function names (e.g., `download_post` instead of `dp`).
- Add comments for complex logic to improve readability.
- Ensure your code is compatible with Python 3.9+ and PyQt6.
- Avoid hardcoding values; use constants or configuration files where appropriate.

## Reporting Bugs
If you find a bug but aren’t ready to fix it, please open an issue on the [Issues page](https://github.com/VoxDroid/KemonoDownloader/issues) with the following details:
- A clear description of the bug.
- Steps to reproduce the issue.
- Expected behavior vs. actual behavior.
- Screenshots or logs, if applicable.
- Your operating system and Python version.

## Suggesting Features
To suggest a new feature, start a thread in the [Discussions tab](https://github.com/VoxDroid/KemonoDownloader/discussions) or open an issue with the label "enhancement." Include:
- A description of the feature and why it would be useful.
- Any potential challenges or considerations.
- Examples or mockups, if applicable.

## Getting Help
If you need help with contributing, check the [Support page](SUPPORT.md) for resources, or ask a question in the [Discussions tab](https://github.com/VoxDroid/KemonoDownloader/discussions).

Thank you for contributing to KemonoDownloader!
