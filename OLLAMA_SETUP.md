# Ollama Configuration Guide for Financial FP&A

## Your Current Setup

Based on your `.env` file, you're using **Ollama** with the model `llama4:sc`.

## Required Environment Variables

For CrewAI to work with Ollama, you need these variables in your `.env` file:

```bash
# Point to your local Ollama server
OPENAI_API_BASE=http://localhost:11434/v1

# Specify your Ollama model name
OPENAI_MODEL_NAME=llama3.1
# OR if you want to use your specific model:
# OPENAI_MODEL_NAME=llama4:sc

# Placeholder API key (required by CrewAI but not used with Ollama)
OPENAI_API_KEY=NA

# Optional: For internet search (Market Research agent)
SERPER_API_KEY=your_serper_api_key_here
```

## What Each Variable Does

| Variable | Purpose | Your Value |
|----------|---------|------------|
| `OPENAI_API_BASE` | URL of Ollama server | `http://localhost:11434/v1` |
| `OPENAI_MODEL_NAME` | Which Ollama model to use | `llama3.1` or `llama4:sc` |
| `OPENAI_API_KEY` | Placeholder (not used) | `NA` or any value |
| `SERPER_API_KEY` | Internet search (optional) | Get from serper.dev |

## Your `.env` File Should Look Like:

```bash
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_MODEL_NAME=llama4:sc
OPENAI_API_KEY=NA
SERPER_API_KEY=your_key_if_you_have_one
```

## Important Notes

1. **Ollama Must Be Running**
   - Make sure Ollama is running: `ollama serve`
   - Verify it's accessible: `curl http://localhost:11434/v1/models`

2. **Model Must Be Pulled**
   - Ensure your model is downloaded: `ollama pull llama4:sc`
   - Or use a different model: `ollama pull llama3.1`

3. **No OpenAI Account Needed**
   - You don't need an OpenAI API key
   - Everything runs locally on your machine
   - No external API costs

4. **Internet Search (Optional)**
   - Only needed for Market Research agent
   - Other agents work fine without it
   - Free tier available at serper.dev

## Verification

After updating your `.env` file:

1. **Check Ollama is running:**
   ```bash
   curl http://localhost:11434/v1/models
   ```

2. **Restart Streamlit app:**
   - Stop current app (Ctrl+C)
   - Run: `streamlit run streamlit_app.py`

3. **Check sidebar in app:**
   - Should show API configuration status
   - Green checkmark = configured correctly

## Troubleshooting

**Issue:** "Connection refused" error
**Solution:** Start Ollama server: `ollama serve`

**Issue:** "Model not found"
**Solution:** Pull the model: `ollama pull llama4:sc`

**Issue:** Agents not responding
**Solution:** Verify `OPENAI_API_BASE` points to `http://localhost:11434/v1`
