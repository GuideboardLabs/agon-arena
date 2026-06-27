# The 8GB VRAM King

## What happens when you put four local language models through 18 tasks, 3 runs each, and let the numbers speak.

I have been running local language models on an AMD RX 5700 XT for a while now. Eight gigabytes of VRAM. Not a lot by datacenter standards, but it is the most common GPU in the local LLM space. The Steam Hardware Survey puts the 8GB class at the top of the charts. If you are running models at home, this is probably what you have.

The question is simple. Given 8GB of VRAM, which model gives you the most capability?

I built a benchmark to find out. Three events. Agent, Reason, Code. 18 tasks total, 54 points maximum. Hidden test grading so the models cannot cheat. Three runs per model per event, reported as the mean. All models at Q4_K_M quantization on the same GPU, same driver, same llama.cpp build.

And then something interesting happened. A new model appeared in the 9B weight class. Ornith-1.0-9B. It was not the biggest model in the test. It was not the smallest. But it had a claim that caught my attention. It was supposed to be something special.

I had to find out.

---

## The Contenders

Four models made the final cut.

**Gemma4-12B** (6.3GB). Google's latest. The biggest model that still fits in 8GB at Q4_K_M. It has the most parameters, the most layers, the most everything. It also has the hardest time fitting. At 21.6 tokens per second, it is the slowest model in the test by a wide margin. The GPU is swapping layers in and out of VRAM. It works, but it is not happy about it.

**Ornith-1.0-9B** (5.3GB). The newcomer. A 9B parameter model that appeared with very little fanfare. No big company behind it. No press release. Just a GGUF file on Hugging Face and a claim that it punches above its weight class. I downloaded it out of curiosity. It ended up being the most interesting model in the test.

**Qwen3.5-9B** (6.3GB). Alibaba's latest in the Qwen line. The same file size as Gemma4-12B despite having 3 billion fewer parameters. That is unusual. It suggests a different architecture or a different quantization approach. It scored well across the board.

**LFM2.5-8B** (5.0GB). The smallest model in the test. It fits entirely in VRAM with room to spare. At 91.1 tokens per second, it is more than four times faster than Gemma4-12B. Speed is not everything, but it is not nothing either.

---

## The Benchmark

I call it Agon-Bench. Three events, six tasks each.

**Agent** (18 points). Tool calling, orchestration, error handling, planning, parsing, decision-making. These are the skills a model needs to actually do things, not just answer questions. Can it call a function with the right arguments? Can it handle an error without falling apart? Can it plan a sequence of steps?

**Reason** (17 points). Logical deduction, math word problems, constraint satisfaction, counterfactual reasoning, analytical explanation, multi-hop synthesis. Pure thinking. No tools, no code. Just the model and a problem.

**Code** (19 points). String cleaner, log parser, LRU cache, file indexer, task runner CLI, constrained diff tool. Real programming tasks with hidden test cases. The model writes the code, the tests grade it. No partial credit for being close.

Every task has hidden tests. The models never see the grading criteria. They just get the prompt and have to produce working output. Three runs per model per event. I report the mean score across all three runs.

---

## The Results

The numbers are in. Here is what they say.

### Overall Scores

| Model | Agent (18) | Reason (17) | Code (19) | Total (54) | Percent |
|-------|:----------:|:-----------:|:---------:|:----------:|:-------:|
| Gemma4-12B | 15.0 | 16.7 | 10.3 | **42.0** | **78%** |
| Qwen3.5-9B | 14.0 | 16.0 | 10.3 | **40.3** | **75%** |
| Ornith-1.0-9B | 11.7 | 16.3 | 12.0 | **40.0** | **74%** |
| LFM2.5-8B | 10.7 | 16.7 | 8.8 | **36.2** | **67%** |

Gemma4-12B wins the overall crown. 42 out of 54. 78 percent. It is the most capable model you can run on 8GB VRAM, full stop.

But the story is not that simple.

### The Agent Event

Gemma4-12B dominates here. 15 out of 18. It is the only model that scored well on Planning and Parsing, two tasks that require the model to think about structure and sequence. Qwen3.5-9B is a distant second at 14. Ornith drops to 11.7. LFM2.5 lands at 10.7.

The gap between Gemma4 and the rest is 3 points. That is the difference between a model that can plan and a model that cannot.

### The Reason Event

This is where things get interesting. Every model scores well on reasoning. LFM2.5-8B, the smallest model in the test, ties Gemma4-12B at 16.7 out of 17. Ornith is right behind at 16.3. Qwen3.5 is at 16.0.

Reasoning is not the bottleneck. Every model in this test can think. The difference is in what they do with that thinking.

### The Code Event

Ornith-1.0-9B takes the lead. 12 out of 19. It beats Gemma4 by nearly 2 points. It beats Qwen3.5 by nearly 2 points. It beats LFM2.5 by more than 3 points.

This is the surprise. A 9B model nobody has heard of, beating a 12B model from Google at code generation. Ornith scored a perfect 5 out of 5 on String Cleaner. It scored 3 out of 3 on LRU Cache. It scored 2 out of 3 on Constrained Diff Tool, the hardest task in the event.

Gemma4 scored 0 on LRU Cache. It scored 0 on Task Runner CLI. It scored 1.3 on Constrained Diff. Ornith beat it on three out of six code tasks.

### The Efficiency Story

This is where LFM2.5-8B makes its case. At 91.1 tokens per second, it is more than four times faster than Gemma4-12B. It generates 200,000 tokens in the same time Gemma4 generates 47,000. If you are doing interactive work, that speed matters.

But speed is not capability. LFM2.5 scores 36.2 out of 54. That is 67 percent. It is last place. It is fast, but it is not as capable.

I included efficiency as a 10 percent weight in a composite score. It bumps LFM2.5 from 67 percent to 70.3 percent. It bumps Gemma4 from 78 percent to 72.4 percent. The ranking does not change. Capability still wins.

---

## The Verdict

There is no single answer. It depends on what you need.

If you need the most capable model you can run on 8GB VRAM, get Gemma4-12B. It scores 42 out of 54. It dominates the Agent event. It is the best all-around model in the test. It is also the slowest at 21.6 tokens per second. You trade speed for capability.

If you need code generation, get Ornith-1.0-9B. It scores 12 out of 19 on the Code event, beating every other model including the 12B. It is fast at 45.4 tokens per second. It is small at 5.3GB. It is the code king of the 8GB class.

If you need raw speed, get LFM2.5-8B. It is 91 tokens per second. It fits entirely in VRAM. It ties Gemma4 on reasoning. But it scores last on agent tasks and code tasks. Speed is not a substitute for capability.

If you need a balanced model that does everything well, get Qwen3.5-9B. It scores 40.3 out of 54. It is second in Agent, third in Reason, second in Code. It is not the best at anything, but it is not the worst at anything either.

---

## The Contender

Ornith-1.0-9B is the most interesting model in this test. It came out of nowhere. It has no big company backing. It has no marketing budget. It just showed up on Hugging Face and started beating models twice its size at code generation.

I do not know who built it. I do not know what data it was trained on. I only know what the numbers say. And the numbers say it is the best code model you can run on 8GB VRAM.

That is worth paying attention to.

---

## The Caveats

This is one benchmark on one GPU. Your results may vary.

The Agent and Reason events were graded against existing response files. The grading scripts were built after the model runs completed. That means the models were not optimized for the grading criteria. It also means the scores are fair, because the models never saw the tests.

The Code event uses hidden test cases. Every model was graded blind. No partial credit. No human judgment. Just pass or fail.

All models were run on a single AMD RX 5700 XT with 8GB VRAM using the Vulkan backend. On 16GB hardware, the speed gap would narrow. Gemma4-12B would fit entirely in VRAM and run faster. But the relative ordering would stay the same. Smaller models are faster. Bigger models are more capable. That is the tradeoff.

---

## What I Learned

The 8GB VRAM class is more competitive than I expected. A year ago, the answer was simple. Get the biggest model that fits. Today, the answer depends on what you are doing.

If you are building agents, get Gemma4-12B. If you are writing code, get Ornith-1.0-9B. If you are doing both, get both. They fit on the same drive. They take the same VRAM. You can swap them in seconds.

The 8GB VRAM king is not one model. It is the model that matches your task.

And the next time a model appears out of nowhere with a claim that sounds too good to be true, test it. You might be surprised.
