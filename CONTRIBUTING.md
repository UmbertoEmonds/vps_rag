# Contributing

Thank you for your interest in contributing to this project!

## Getting Started

1. Fork the repository
2. Clone your fork:

   ```bash
   git clone https://github.com/maxime-lenne/simplon-rag-sample.git
   cd simplon-rag-sample
   ```

3. Install dependencies:

   ```bash
   uv sync --extra dev
   pre-commit install
   ```

## Development Workflow

### Creating a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### Making Changes

1. Make your changes following the project conventions
2. Run linting to ensure code quality:

   ```bash
   uv run pymarkdownlnt scan --recurse .
   uv run yamllint .
   ```

3. Commit your changes:

   ```bash
   git commit -m "feat: add new feature"
   ```

### Commit Convention

This project uses **Conventional Commits**:

`<type>(scope): <description>`

Examples:

- `feat: Add document ingestion pipeline`
- `fix(retriever): Fix pgvector connection timeout`
- `docs: Update README with installation steps`
- `feat!: Breaking change in API`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

### Submitting a Pull Request

1. Push your branch to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a Pull Request against the `develop` branch
3. Fill out the PR template
4. Wait for review

## Code Style

- Follow the existing code style
- Use EditorConfig settings (`.editorconfig`)
- Ensure all linting passes before committing

## Reporting Issues

- Use the issue templates when available
- Provide clear reproduction steps for bugs
- Include environment details when relevant

## Questions?

Feel free to open an issue for any questions or concerns.
