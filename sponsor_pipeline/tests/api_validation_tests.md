# Purpose of test
this file simply provides a few commands to paste in order to test the  looks_like_api_key() function, as well as the other minor changes in error handling found in both `sponsor_pipeline/cli.py `and  `sponsor_pipeline/llm/client.py`. 

## Quick prep (optional): create a tiny urls file for scrape tests
```bash
printf "https://example.com\n" > urls.txt
```

## 1) LLM command, no key set: expect heuristic failure (exit 1, friendly config error)
```bash
LLM_PROVIDER="openai" python3 main.py discover
echo exit:$?
# Expected:Configuration error: API key for llm provider 'openai' appears missing or malformed. Check OPENAI_API_KEY in your .env. exit:1
```

## 2) LLM command, placeholder key** — expect heuristic failure
```bash
LLM_PROVIDER="openai" OPENAI_API_KEY="your-openai-key-here" python3 main.py discover
echo exit:$?
# Expected:Configuration error: API key for llm provider 'openai' appears missing or malformed. Check OPENAI_API_KEY in your .env. exit:1

```


## 3) LLM command, key with whitespace** — expect heuristic failure
```bash
LLM_PROVIDER="openai" OPENAI_API_KEY="abc def 123456" python3 main.py discover
echo exit:$?
# Expected:Configuration error: API key for llm provider 'openai' appears missing or malformed. Check OPENAI_API_KEY in your .env. exit:1
```

## 4) LLM command,  too short key <16 chars** — expect heuristic failure
```bash
LLM_PROVIDER="openai" OPENAI_API_KEY="shortkey" python3 main.py discover
echo exit:$?
# Expected:Configuration error: API key for llm provider 'openai' appears missing or malformed. Check OPENAI_API_KEY in your .env. exit:1
```

## 5) LLM command, valid-looking key   heuristic passes; pipeline proceeds (may later surface provider auth error at runtime)
```bash
LLM_PROVIDER="openai" OPENAI_API_KEY="ak_1234567890abcdef" python3 main.py discover
echo exit:$?
# Expected: CLI does NOT fail on heuristic (exit code depends on downstream run).
#Configuration error: LLM authentication failed for provider 'openai'. Check OPENAI_API_KEY in your .env and ensure it is a valid key. exit:1
```


## 6) Scrape (no LLM required): should run even without LLM keys
```bash
python3 main.py scrape --url "https://example.com"
echo exit:$?
# Expected: runs scrape path (no API key, no heuristic check), exit:0
```

