#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Installs tools/leak-check.py for the maintainer of this repository: a
# copy of the script and three git hooks under ~/.config/bagofwaffles/,
# which every clone of the project on this machine then uses. It changes
# no git or Claude Code configuration: it prints what to add.
#
# Usage: tools/leak-check-install.sh
#
# Run it again after tools/leak-check.py changes.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
home=${WB_LEAK_CONFIG:-$HOME/.config/bagofwaffles}
shown=$(printf '%s' "$home" | sed "s|^$HOME|~|")

umask 077
mkdir -p "$home/hooks"
cp "$here/leak-check.py" "$home/leak-check.py"
for hook in pre-commit commit-msg pre-push; do
	cat > "$home/hooks/$hook" <<EOF
#!/bin/sh
exec python3 -I -B "$home/leak-check.py" $hook "\$@"
EOF
	chmod 700 "$home/hooks/$hook"
done
if [ ! -e "$home/leak-patterns" ]; then
	cat > "$home/leak-patterns" <<'EOF'
# One regular expression a line, matched without regard to case, against
# every file, message, ref name and GitHub post. Never tracked anywhere.
# Put here what must not get out: names, addresses, domains, host names.
# A pattern that also matches upstream code in src/third_party/ blocks it too,
# so prefer the distinctive ones.
EOF
fi
[ -e "$home/banned-commits" ] || : > "$home/banned-commits"

cat <<EOF
Installed in $shown.

1. Git, in ~/.gitconfig, so that any clone of the project gets the project
   identity and the hooks wherever it lies:

	[includeIf "hasconfig:remote.*.url:git@github.com:bagofwaffles/**"]
		path = ~/.gitconfig_bagofwaffles
	[includeIf "hasconfig:remote.*.url:https://github.com/bagofwaffles/**"]
		path = ~/.gitconfig_bagofwaffles
	[includeIf "hasconfig:remote.*.url:ssh://git@github.com/bagofwaffles/**"]
		path = ~/.gitconfig_bagofwaffles

   and in ~/.gitconfig_bagofwaffles, beside the identity:

	[core]
		hooksPath = $shown/hooks

   Safer still: keep no [user] name or email in ~/.gitconfig at all, give
   each of your other work folders its own includeIf, and set
   "[user] useConfigOnly = true", so a clone git does not recognize
   cannot commit.

2. Claude Code, in ~/.claude/settings.json:

	"attribution": {"commit": "", "pr": "", "sessionUrl": false},
	"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{
		"type": "command", "onFailure": "block", "timeout": 20,
		"command": "python3 -I -B $shown/leak-check.py claude-hook"}]}]}

3. Your patterns, in $shown/leak-patterns.

The state of this clone:

EOF
python3 -I -B "$home/leak-check.py" doctor || true
