@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   Кто сегодня работает?
echo.

if not exist ".git" (
  echo   Ошибка: это не репозиторий.
  echo   Открой проект в PyCharm и запусти select-me из его Terminal.
  echo.
  pause
  exit /b 1
)

git --version >nul 2>&1
if errorlevel 1 (
  echo   Ошибка: git не найден. Скажи учителю.
  echo.
  pause
  exit /b 1
)

set "login="
set /p "login=Твой логин: "

if "%login%"=="" (
  echo   Логин не введён.
  echo.
  pause
  exit /b 1
)

if not exist "students\%login%" (
  echo.
  echo   Ошибка: папки students\%login% нет.
  echo.
  echo   Доступные папки:
  for /d %%D in (students\*) do echo       %%~nxD
  echo.
  pause
  exit /b 1
)

set "name="
if exist "students\%login%\name.txt" (
  for /f "usebackq delims=" %%L in ("students\%login%\name.txt") do (
    if not defined name set "name=%%L"
  )
)
if not defined name set /p "name=Как тебя зовут (попадёт в историю коммитов): "
if not defined name (
  echo   Имя не задано.
  echo.
  pause
  exit /b 1
)

git config user.name "%name%"
git config user.email "%login%@class.local"

echo.
echo   Готово. Твои коммиты будут подписаны так:
echo.
git config --get user.name
git config --get user.email
echo.
pause
