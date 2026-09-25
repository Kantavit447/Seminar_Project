<user> You are given a task of grading the quality of the answer made by a student about a verdict of a case. You are given the student answer under the tag <student_answer> and the reference answer you reached under the tag <reference_answer>. You are also provided with <ข้อหารือ> as case detail you reference something with in case some entities are abbreviated. You need to evaluate the quality of the student answer based on two metrics.
1. Coverage: How much does the student answer covered the reference answer? High quality answer should covers all aspect of the reference answer and only that. This metric has only 3 grades: no-coverage, partial-coverage, full-coverage
    1.1 no-coverage: The student answer does not cover any aspect of the reference answer. It can be either wrong or irrelevant to the question
    1.2 partial-coverage: The student answer covers some aspect of the reference answer or all aspect of the reference answer but with a high amount of irrelevant information inbetween.
    1.3 full-coverage: The student answer covers all aspect of the reference answer and contains few to no irrelevant information inbetween.
2. Contradiction: Is the student answer contradicting the reference answer or the relevant law content or itself? High quality answer should not contradict either the reference answer, the law or itself. This metric differs from the above metric in some cases. For example, a student answer can have partial coverage score while still contradicting the reference answer. Also, a student answer can also have no coverage score while still not contradicting the reference answer in the case where the student answer only contains irrelevant information. This metric only has 2 grades: no-contradiction, contradiction
    2.1 no-contradiction: The student answer does not contradict the reference answer and itself
    2.2 contradiction: The student answer contradicts the reference answer or itself in any aspect of the answers

DO NOT ATTEMPT TO ASSIGN OTHER SCORE THAN THE ONE LISTED!!!

Here's the full instruction of how to do this task:
1. First, check out the <student_answer> and <reference_answer> and <ข้อหารือ>, to estimate what points they are making first and put the thoughts in the key <student_points> and <reference_points>. BE CAREFUL, SOMETIMES THE POINTS ARE NOT SPECIFIED EXPLICITLY SUCH AS "การให้บริการทั้งสองแบบนั้นต้องเสียภาษี" WHICH SHOULD BE SPLITTED INTO "การให้บริการแบบแรกต้องเสียภาษี" AND "การให้บริการแบบที่สองต้องเสียภาษี"
2. From the points extracted, measure the two metrics. If student covers only some points of reference, the score is partial-coverage. If all, it's full-coverage. If none, it's no-coverage. As for contradiction, if any student point contradicts with itself or the reference points or the law, it's contradiction. Otherwise, it's no-contradiction.
    
YOU MUST PROVIDE YOUR RESPONSE IN JSON STRUCTURE AS FOLLOWING:
{"point_thought": "(str) Your rationale on how to split reference answers and student answers into list of points made" ,
  "student_points": "(List[str]) List of string representing each point the student answer made",
  "reference_points": "(List[str]) List of string representing each point the reference answer made",
  "coverage": {"thought": "(str) Your thought on how you evaluate the student points and reference points on the coverage aspect and what score should you give", "score": "(str) Final coverage score of the student answer. Should only be 1 of 3 grades: no-coverage, partial-coverage or full-coverage"},
  "contradiction": {"thought": "(str) Your thought on how you evaluate the student points and reference points on the contradiction aspect and what score should you give", "score": "(str) Final contradiction score of the student answer. Should only be 1 of 2 grades: no-contradiction or contradiction"}
}


Caution:
    1. MAKE SURE TO PROVIDE A REASONABLE THOUGHT PROCESS AS WELL.
    2. BE CAREFUL NOT TO CONSIDER THE ACCURACY OF CITATION OF THE LAW IN THE ANSWER IN BOTH CONTRADICTION AND COVERAGE METRICS. THERE IS A SEPARATE METRIC FOR THAT. FOR EXAMPLE, IF A STUDENT ANSWER "บริษัทไม่ต้องจ่ายภาษีตามมาตรา 82/1 ประมวลรัษฎากร" BUT THE REFERENCE USE SECION 82/2 INSTEAD BUT OTHERWISE IS THE SAME. THE COVERAGE SCORE IS full-coverage WHILE THE CONTRADICTION SCORE IS no-coverage. PLEASE BE VERY CAREFUL OF THIS!!!. THE OMISSION OF LAW IN STUDENT ANSWER IS ALSO FINE IF THE MAIN POINT IS STILL THE SAME
    3. *** THIS IS REALLY IMPORTANT!! *** IF THE STUDENT'S ANSWER CONTAINS ADDITIONAL INFORMATION THAT IS NOT COVERED BY THE REFERENCE ANSWER AND IT IS NOT CONTRADICTING ANY POINT OF THE REFERENCE ANSWER, YOU MUST NOT USE THE EXCESS INFORMATION TO COUNT TOWARDS THE COVERAGE SCORE. FOR EXAMPLE, IF THE STUDENT MAKES THE POINT a and b AND THE REFERENCE MAKES POINT a. THE STUDENT WOULD STILL GET full-coverage score
    4. *** THIS IS IMPORTANT *** IF THE STUDENT MISSES SOMETHING FROM REFERENCE ANSWER POINTS WHICH ARE NOT DIRECTLY ASKED OR NOT A CRUCIAL PART OF REFERENCE ANSWER. THE COVERAGE SCORE WOULD NOT BE AFFECTED OR DEDUCED BY IT. FOR EXAMPLE, IF STUDENT MAKES point a WHILE REFERENCE MAKES point a, b and point b is not important part of the answer and it is not asked in the question. THE STUDENT WOULD STILL GET full-coverage

If you do this task well and provide good thought process and accurate classification, I will tip you 200 US Dollar!
    
Take a deep breath and think carefully. Think in gradually increasing complexity

<assistant> I will strictly adhere to the guidelines you told me for this task
