#!/data/data/com.termux/files/usr/bin/sh
# One-time launcher installer. Run in the ordinary Termux shell, NOT in proot.
set -eu

if ! command -v proot-distro >/dev/null 2>&1; then
    echo "Не найден proot-distro. Установи: pkg install proot-distro"
    exit 1
fi

PREFIX="/data/data/com.termux/files/usr"
mkdir -p "$PREFIX/bin"

cat > "$PREFIX/bin/forge" <<'FORGE_LAUNCH'
#!/data/data/com.termux/files/usr/bin/sh
# One command: Termux -> Ubuntu -> correct venv -> terminal application.
exec proot-distro login ubuntu -- /bin/bash -c '
    export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    cd /root/agentforge-ayu || { echo "Не найден /root/agentforge-ayu"; exit 1; }
    [ -x .venv/bin/python ] || { echo "Нет Python окружения .venv"; exit 1; }
    exec .venv/bin/python -m contentforge.terminal_app
'
FORGE_LAUNCH
chmod 755 "$PREFIX/bin/forge"

echo "Команда forge установлена."
echo "Теперь введи: forge"
echo "Первый запуск: открой 'Система' и сохрани ключ OpenRouter."
