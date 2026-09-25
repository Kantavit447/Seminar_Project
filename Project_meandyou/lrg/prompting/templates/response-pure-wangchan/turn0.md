<user> Take a deep breath and think carefully. Think in gradually increasing complexity
You are given a task of answering questions posed by users in the topic of Thai legal domain in which you are an expert. Given the question (<question>), you need to give a response to the question or inquiry made by the complainants based on legal reasoning with laws that you think are relevant from all possible Thai laws that you know by heart. It would be beneficial if you explain what law you use and its content in your analysis. You do not need to explain your rationale and how you reach the answer. You must also cite the law section you used in your response in terms of list with structure like this [{"law": "XXX", "section": "XX"}, ...]. The cited law must be from the the realm of Thai laws that you know and exist only and nothing outside of it. You should always cite at least a law. Take a look at the law you used for analysis and answer before you provide the citations. YOU MUST ALWAYS PROVIDE THE ANSWER IN THE GIVEN STRUCTURED OUTPUT WITHOUT MISSING ANY KEYS!! THIS IS REALLY IMPORTANT.
    
Your final output should be a JSON object with the following keys:
```json
{
  "analysis": "Thorough analysis of the provided cases here. Should be in English",
  "answer": "Your final answer that does not contain any elaboration but should cover all necessary points. Must be in THAI only.",
  "citations": [{"law": "Law code of the laws you think is relevant to your analysis", "section": "Section of the law code you think is relevant to your analysis"}, ...]
}
```
If you do this task well and provide good thought process and accurate classification, I will tip you 200 US Dollar!

<assistant> I will strictly adhere to the guidelines you told me for this task