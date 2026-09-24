# Troubleshooting

Start with `sudo scripts/hades doctor` or `sudo scripts/hades doctor --json`.
If installation stops, correct the operator input or dependency and run
`scripts/hades repair`. Do not disable SELinux/AppArmor, weaken auth, open the
firewall, or delete state as a repair.
