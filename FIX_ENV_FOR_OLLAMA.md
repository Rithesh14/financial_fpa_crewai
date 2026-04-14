# URGENT: Fix Your .env File for Ollama

## Problem
CrewAI is trying to use OpenAI API instead of your local Ollama server.

## Solution
Update your `.env` file with these EXACT lines:

```bash
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_MODEL_NAME=llama3.1
OPENAI_API_KEY=NA
```

## Step-by-Step Instructions

1. **Open your `.env` file** in the project root directory

2. **Replace ALL contents** with:
   ```
   OPENAI_API_BASE=http://localhost:11434/v1
   OPENAI_MODEL_NAME=llama3.1
   OPENAI_API_KEY=NA
   ```

3. **Save the file**

4. **Verify Ollama is running:**
   ```bash
   ollama serve
   ```
   
5. **Verify your model is available:**
   ```bash
   ollama list
   ```
   If you see `llama4:sc` instead of `llama3.1`, use that:
   ```
   OPENAI_MODEL_NAME=llama4:sc
   ```

6. **Restart Streamlit:**
   - Stop current app (Ctrl+C)
   - Run: `streamlit run streamlit_app.py`

## Why This Works

- `OPENAI_API_BASE` tells CrewAI to use Ollama instead of OpenAI
- `OPENAI_MODEL_NAME` specifies which Ollama model to use
- `OPENAI_API_KEY=NA` is a placeholder (Ollama doesn't need a real API key)

## Verification

After updating `.env`:
1. Restart Streamlit
2. Check sidebar - should show "✅ Ollama (Local LLM)"
3. Upload CSV and run analysis
4. Should work without authentication errors

## Important Notes

- Make sure Ollama is running (`ollama serve`)
- Make sure your model is pulled (`ollama pull llama3.1` or `ollama pull llama4:sc`)
- The `.env` file is in the root directory: `c:\Users\RitheshS\Desktop\financial_fpa\.env`
