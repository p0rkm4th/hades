# HADES quickstart

HADES is a self-hosted household assistant for local chat, memory, inventory,
recipes, bounded web research, and optional automation.

```sh
curl -fsSL https://raw.githubusercontent.com/p0rkm4th/Hades/main/install.sh | \
  bash -s -- install --inputs /etc/hades/operator-inputs.env
```

Review and pin `HADES_REPO_REF` first for a prerelease. The setup creates a
fresh owner identity and never imports another deployment's state or secrets.
See [`INSTALL.md`](INSTALL.md).
