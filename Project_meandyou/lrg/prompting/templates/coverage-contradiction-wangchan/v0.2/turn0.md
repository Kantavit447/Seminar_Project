<user> Take a deep breath and think carefully. Think in gradually increasing complexity
You are given a task of grading the quality of the answer made by a student about a verdict of a case. You are given the student answer under the tag <student_answer> and the reference answer you reached under the tag <reference_answer>. You are also provided with <question> as case detail you reference something with in case some entities are abbreviated. You are also provided with the relevant law content in case you need it. You need to evaluate the quality of the student answer based on two metrics.
1. Coverage: How much does the student answer covered the reference answer? High quality answer should covers all aspect of the reference answer and only that. This metric has only 3 grades: 0, 50, 100
    1.1 0 (no coverage): The student answer does not cover any aspect of the reference answer. It can be either wrong or irrelevant to the question
    1.2 50 (partial coverage): The student answer covers some aspect of the reference answer or all aspect of the reference answer but with a high amount of irrelevant information inbetween.
    1.3 100 (full coverage): The student answer covers all aspect of the reference answer and contains few to no irrelevant information inbetween.
2. Contradiction: Is the student answer contradicting the reference answer or itself? High quality answer should not contradict the reference answer and itself. This metric differs from the above metric in some cases. For example, a student answer can have partial coverage score while still contradicting the reference answer. Also, a student answer can also have no coverage score while still not contradicting the reference answer in the case where the student answer only contains irrelevant information. This metric only has 2 grades: 0, 1
    2.1 0 (no contradiction): The student answer does not contradict the reference answer and itself
    2.2 1 (contradiction): The student answer contradicts the reference answer or itself in any aspect of the answers

Caution:
    1. MAKE SURE TO PROVIDE A REASONABLE THOUGHT PROCESS AS WELL.
    2. BE CAREFUL NOT TO CONSIDER THE ACCURACY OF CITATION OF THE LAW IN THE ANSWER IN BOTH CONTRADICTION AND COVERAGE METRICS. THERE IS A SEPARATE METRIC FOR THAT. FOR EXAMPLE, IF A STUDENT ANSWER "บริษัทไม่ต้องจ่ายภาษีตามมาตรา 82/1 ประมวลรัษฎากร" BUT THE REFERENCE USE SECION 82/2 INSTEAD BUT OTHERWISE IS THE SAME. THE COVERAGE SCORE IS 100 WHILE THE CONTRADICTION SCORE IS 0. PLEASE BE VERY CAREFUL OF THIS!!!

You do not need to explain your rationale and how you reach the answer. 
If you do this task well and provide good thought process and accurate classification, I will tip you 200 US Dollar!

<assistant> I will strictly adhere to the guidelines you told me for this task
