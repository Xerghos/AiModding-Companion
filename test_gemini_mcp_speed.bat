@echo off
setlocal

REM Config
set "MCP_PORT=8000"
set "MCP_HOST=127.0.0.1"

REM Temp dir
set "TEST_DIR=temp_gemini_test"
mkdir "%TEST_DIR%" 2>nul
mkdir "%TEST_DIR%\.gemini" 2>nul

REM Create settings.json
(
echo {
echo   "mcpServers": {
echo     "aimodding-tools": {
echo       "url": "http://%MCP_HOST%:%MCP_PORT%/mcp",
echo       "trust": true,
echo       "timeout": 60000
echo     }
echo   }
echo }
) > "%TEST_DIR%\.gemini\settings.json"

REM Create dummy prompt
echo Hello > "%TEST_DIR%\prompt.txt"

REM Run gemini-cli
echo Testing Gemini CLI with MCP at %MCP_HOST%:%MCP_PORT%...
echo Start: %TIME%

cd "%TEST_DIR%"
call gemini --model gemini-2.0-flash-exp --output-format text < prompt.txt

echo End: %TIME%
cd ..
rmdir /s /q "%TEST_DIR%"
endlocal
