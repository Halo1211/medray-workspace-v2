# MedRay v2 Wiki Source

This folder contains Markdown pages prepared for the GitHub Wiki. GitHub Wikis are stored in a separate `repository.wiki.git` repository, so these files are kept in the main repository as a reviewable source of truth.

## Publishing to GitHub Wiki

1. Enable **Wikis** in the repository's GitHub settings.
2. Clone the wiki repository shown by GitHub:

   ```bash
   git clone https://github.com/OWNER/REPOSITORY.wiki.git
   ```

3. Copy the contents of this folder into the wiki clone.
4. Commit and push the wiki pages.

Replace `OWNER/REPOSITORY` with the real GitHub repository path. Keep the main [README](../README.md) and the files in `docs/` as the canonical project documentation; the wiki is an easier-to-navigate presentation of the same supported behavior and safety boundaries.

## Pages

- [Home](Home.md)
- [Getting Started](Getting-Started.md)
- [User Guide](User-Guide.md)
- [Architecture](Architecture.md)
- [Safety and Privacy](Safety-and-Privacy.md)
- [Model Integration](Model-Integration.md)
- [Validation Workbench](Validation-Workbench.md)
- [Troubleshooting](Troubleshooting.md)
- [Contributing](Contributing.md)
