<user> Take a deep breath and think carefully. Think in gradually increasing complexity.

Your task is to retrieve the relevant sections of law codes related to Thai Financial Laws that could be used for solving consultation cases related to the Thai Tax Cases. There are a total of 36 law codes you could retrieve sections from. When you retrieve each sections, you need to specify both the section number and the law code. For each case (referred to as "question" or "ข้อหารือ"), your objective is to identify and extract the relevant sections of the 36 Thai Financial Laws that can be applied. Multiple sections may be applicable, so carefully evaluate each case. Provide a detailed and accurate response (referred to as "retrieved") that aligns with the principles of the Thai Financial Laws. Rank the retrieved responses with the most relevant ones first and you must retrieve 20 unique most relatable section. Please explain your reasoning thoroughly, clearly outlining how each section you reference applies to the specific circumstances of the case. Ensure your response is well-structured and follows logical steps to arrive at the conclusion. Consider including examples or hypothetical scenarios to illustrate your reasoning and make your explanations more concrete. This will help clarify the application of the law in various contexts.

You are provided with the following elements:
    - Law codes: Represents all the possible sections of every law code you can retrieve. You must not retrieve anything outside of this set. The law codes is structured between <ข้อกฎหมาย> and <\ข้อกฎหมาย>. Each law section is provided in <law section=XXX law_name=XXX> </law> with section referring to the name of the section and law_name referring to the law code. You must specify both law code and section name when you retrieve.

Your Task: You will complete the following steps:
1. Understand the Consultation Question:
   - Read the question carefully to grasp the issue at hand.
   - Identify key terms and phrases that highlight the specific concerns of the individual or entity involved.
   - Determine the issue or topics that you need to be careful about and must link it to the relevant laws that contains content about them.

2. Reformulate the Question:
   - This step is to ensure that the provided question is not too hard to query on. You must transform the provided query into a more concise and explicit ones so that you can retrieve relevant laws much more easily.
   - Transform the question into a clear and precise legal question.
   - Use technical legal language that aligns with the Thai Financial Laws
   - Ensure the reformulated question directly addresses the legal issue to facilitate a focused response.
   - Put this in the key of "reformulated_question"
   - When retrieving, take a look at both reformulated_question and the original question since the reformulated one might miss some details

3. Conduct Legal Research:
   - Analyze the situation to pinpoint relevant sections and sections of the Thai Financial Laws.
   - Familiarize yourself with the format of the law sections, typically noted as "มาตรา {number} {none, ทวิ, ตรี, จัตวา, ฉ, ... etc.}"
   - Research specific provisions that govern the identified financial issue, taking note of any rules, exemptions, or limitations.

4. Identify Applicable sections:
   - List potential sections that could apply to the case based on your research.
   - Consider multiple sections that may be relevant to the scenario, ensuring you do not repeat any laws already discussed in previous cases.
   - Remind yourself of what sections are already retrieved by listing out in a tuple format of [(section, law_code), ...] for every section retrieved in previous ranks
   - Put how you think this section is relevant and what rank out of 20 (This number might change in the case you make a mistake of retrieving duplicated laws) is this section so you can keep track of the number of laws you retrieved in the key "reasoning".
   - Caution, DO NOT PROCESS SUBSECTIONS AS ONE RETRIEVED LAWS. THE SMALLEST UNIT OF RETRIEVED ITEM IS A SECTIOn. DO NOT RETRIEVE DUPLICATE SECTIONS!!!
   - Double check if your retrieved sections is duplicate. Put it as boolean in the key of "already_retrieved"!

5. Draft a Detailed Response:
   - Formulate your answer based on the selected sections.
   - Outline how each section applies to the case, breaking down the reasoning step by step.
   - Maintain logical structure: Start with the general rule, followed by any exceptions or conditions.

6. Include Examples or Hypotheticals:
   - Incorporate examples or hypothetical scenarios that illustrate the application of the law.
   - Ensure these examples align with the specifics of the user’s question to enhance clarity and understanding.
   - This should be put in the key "example" 

7. Review and Revise:
   - Cross-check your response against the principles of the Thai Financial Laws to ensure accuracy and compliance.
   - Verify that no laws have been reused from previous responses, maintaining diversity in legal references.
   - Retrieved laws cannot be duplicated.
   - Revise your answer for comprehensiveness and clarity, ensuring it fully addresses the user’s concerns.

8. Conclude with a Summary:
   - Summarize the key points of your response, reiterating how the identified sections resolve the legal issue.
   - Highlight the implications of the laws applied to the specific case.


Output: Return your reasoning and results in the following JSON structure. YOU CANNOT MISS ANY KEYS:
{
  "reformulated_question": "string, representing how you reformulate the question for easier retrieval",
  "retrieved": [
    {
      "reasoning": "string, describing the content or purpose of the section and explaining how this section applies to the specific circumstances of the case. Your retrieved section should be chunked as provided in context with each section inbetween <law section=XXX law_name=XXX></law>. Be as thorough as possible. Double-check that your retrieved section is not already retrieved in previous ranks",
      "example": "string, providing a hypothetical scenario or example that illustrates the application of the law"
      "section": "string, representing the section name of the law you retrieved. These are from the section part in <law section=XXX law_name=XXX> of the provided context of your retrieved law. Do not output any extra characters whatsoever.",
      "law_code": "string, representing the law name of the law you retrieved. These are from the law_name part in <law section=XXX law_name=XXX> of the provided context of your retrieved law. Do not output any extra characters whatsoever.",
      "already_retrieved": "boolean, you must explicitly check whether this law is already retrieved in previous ranks or not. You must avoid retrieving duplicated laws at all cost. However, if you cannot avoid it, retrieve more. For example, if of 20 laws, you got 2 duplicated laws. You must retrieve one more so that you have 20 unique relevant laws. This can be either False or True"
    },
    ...
  ],
}
    
CAUTION: DO NOT ANALYSE A SUBSECTION AS A RETRIEVED LAW BY ITSELF. FOR EXAMPLE, DON'T TREAT มาตรา 40 ก AS ONE SECTION SINCE DOING SO WILL LEAD YOU TO RETRIEVE THE SAME มาตรา 40 OVER AND OVER AGAIN. REMIND YOURSELF DURING REASONING ON WHAT SECTIONS FROM WHAT LAWS HAVE YOU RETRIEVED ALREADY!!

Please retrieve at least 20 unique relevant sections for this consultation case.

Good luck! You can do this! I will tip you 100 USD if you can approximate real-world cases from the given content perfectly. And an extra 200 USD if you can accurately retrieve the relevant sections of the Thai Financial Laws of each task!