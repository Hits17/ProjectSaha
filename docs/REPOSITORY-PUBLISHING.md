# ProjectSaha repository publishing

Prepared 2026-11-01 for <https://github.com/Hits17/ProjectSaha.git>.

The complete source snapshot is prepared at
`/home/hitarth/Downloads/ProjectSaha-publish` on branch `main`, with the requested
repository configured as `origin`. Upload is pending: this execution environment
cannot resolve `github.com`. Remote contents and authentication are unverified.

The original host checkout (`/home/hitarth/Downloads/saha`) and its nested frontend
Git repository are preserved. The publication checkout contains the frontend as
ordinary tracked files rather than an unresolved gitlink. It includes current
frontend, admin and backend source, lockfiles, tests, migrations, deployment
templates and documentation, including the interactive references and archives.
It is a fresh snapshot commit; original development history stays in the host
repositories. No application services are restarted by publishing source.

Local environment files, generated credentials, dependencies, build outputs,
databases, backups and nested `.git` directories are excluded. Example environment
files and deliberate test-only credentials remain. Checks cover secret patterns
and comparison with configured host secret values; these are not a guarantee that
every possible secret format is detectable. Keep production configuration private.

From a normal terminal with GitHub connectivity and your Git authentication:

```sh
cd /home/hitarth/Downloads/ProjectSaha-publish
git push -u origin main
```

This is a normal push, never a force push. If GitHub already has a conflicting
`main` history or branch protections, stop and reconcile that remote history or
publish through its required pull request workflow. Do not overwrite the remote.
If authentication is required, use Git's credential manager, GitHub CLI or an SSH
key; do not put access tokens in remote URLs, source files or documentation.

For future changes made in the original host checkout, refresh the publication
snapshot deliberately before pushing; the directories do not synchronize
automatically. A GitHub upload also does not replace the separate build, migration,
service activation and served-version checks in [Hosting](HOSTING.md).
