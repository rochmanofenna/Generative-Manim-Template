from manim import *
from math import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


class GenScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))

        # ---------------- 1. Concept Definition ----------------
        title = Tex("Central Limit Theorem with Dice")
        title.scale_to_fit_width(config.frame_width * 0.8).to_edge(UP)

        definition = Tex(
            "Sums of many independent random variables become bell shaped."
        )
        definition.scale_to_fit_width(config.frame_width * 0.85)

        with self.voiceover(
            text="The central limit theorem says that when we add up many independent random variables, the totals become bell shaped."
        ) as tracker:
            self.play(Write(title), FadeIn(definition), run_time=tracker.duration)

        self.wait(0.5)
        self.play(FadeOut(definition))

        # ---------------- 2. Formula Breakdown ----------------
        formula = MathTex(
            r"S_n = X_1 + X_2 + \cdots + X_n"
        ).scale(1.1)
        formula2 = MathTex(
            r"\frac{S_n - n\mu}{\sigma \sqrt{n}} \; \longrightarrow \; \mathcal{N}(0,1)"
        ).scale(1.1)
        group = VGroup(formula, formula2).arrange(DOWN, buff=0.8)
        group.scale_to_fit_width(config.frame_width * 0.7).move_to(ORIGIN)

        with self.voiceover(
            text="Let S n be the sum of n dice. After subtracting the mean and dividing by the standard deviation, its distribution approaches the standard normal curve."
        ) as tracker:
            self.play(Write(group), run_time=tracker.duration)

        params = MathTex(r"\mu = 3.5, \qquad \sigma^2 = \frac{35}{12}").scale(0.9)
        params.next_to(group, DOWN, buff=0.7)

        with self.voiceover(
            text="For one fair die, the mean is three point five and the variance is thirty five over twelve."
        ) as tracker:
            self.play(FadeIn(params), run_time=tracker.duration)

        self.wait(0.3)
        self.play(FadeOut(group), FadeOut(params))

        # ---------------- 3. Charts ----------------
        # One die
        vals1 = [16.7] * 6
        names1 = ["1", "2", "3", "4", "5", "6"]
        chart1 = BarChart(
            values=vals1,
            bar_names=names1,
            y_range=[0, 20, 5],
            y_length=4,
            x_length=8,
            bar_colors=[BLUE],
        ).scale(0.7).to_edge(DOWN)
        label1 = Tex("One die: flat distribution").scale(0.8).next_to(title, DOWN, buff=0.4)

        with self.voiceover(
            text="A single die is completely flat. Every face from one to six has the same chance, about sixteen point seven percent."
        ) as tracker:
            self.play(Create(chart1), FadeIn(label1), run_time=tracker.duration)

        # Two dice
        counts2 = [1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]
        vals2 = [round(c / 36 * 100, 1) for c in counts2]
        names2 = [str(i) for i in range(2, 13)]
        chart2 = BarChart(
            values=vals2,
            bar_names=names2,
            y_range=[0, 20, 5],
            y_length=4,
            x_length=9,
            bar_colors=[GREEN],
        ).scale(0.7).to_edge(DOWN)
        label2 = Tex("Two dice: a triangle appears").scale(0.8).next_to(title, DOWN, buff=0.4)

        with self.voiceover(
            text="Add a second die and the shape becomes a triangle, peaking at seven, because more combinations give middle totals."
        ) as tracker:
            self.play(
                ReplacementTransform(chart1, chart2),
                ReplacementTransform(label1, label2),
                run_time=tracker.duration,
            )

        # Three dice
        counts3 = [1, 3, 6, 10, 15, 21, 25, 27, 27, 25, 21, 15, 10, 6, 3, 1]
        vals3 = [round(c / 216 * 100, 1) for c in counts3]
        names3 = [str(i) for i in range(3, 19)]
        chart3 = BarChart(
            values=vals3,
            bar_names=names3,
            y_range=[0, 15, 5],
            y_length=4,
            x_length=10,
            bar_colors=[YELLOW],
        ).scale(0.7).to_edge(DOWN)
        label3 = Tex("Three dice: a bell curve forms").scale(0.8).next_to(title, DOWN, buff=0.4)

        with self.voiceover(
            text="With three dice the corners smooth out and a bell curve already begins to appear. More dice make the fit even better."
        ) as tracker:
            self.play(
                ReplacementTransform(chart2, chart3),
                ReplacementTransform(label2, label3),
                run_time=tracker.duration,
            )

        self.wait(0.3)
        self.play(FadeOut(chart3), FadeOut(label3), FadeOut(title))

        # ---------------- 4. Case Study ----------------
        case_title = Tex("Case study: rolling thirty dice").scale(0.9).to_edge(UP)
        step1 = MathTex(r"n = 30, \quad \mu = 3.5").scale(0.9)
        step2 = MathTex(r"E[S_{30}] = 30 \times 3.5 = 105").scale(0.9)
        step3 = MathTex(r"\mathrm{Var}(S_{30}) = 30 \times \frac{35}{12} = 87.5").scale(0.9)
        step4 = MathTex(r"\sigma = \sqrt{87.5} \approx 9.35").scale(0.9)
        steps = VGroup(step1, step2, step3, step4).arrange(DOWN, buff=0.5).move_to(ORIGIN)

        with self.voiceover(
            text="Suppose we roll thirty dice. The expected total is thirty times three point five, which equals one hundred five."
        ) as tracker:
            self.play(FadeIn(case_title), Write(step1), Write(step2), run_time=tracker.duration)

        with self.voiceover(
            text="The variance is thirty times thirty five over twelve, which is eighty seven point five, so the standard deviation is about nine point three five."
        ) as tracker:
            self.play(Write(step3), Write(step4), run_time=tracker.duration)

        result = Tex("So most totals land between about 86 and 124.").scale(0.8)
        result.next_to(steps, DOWN, buff=0.6)

        with self.voiceover(
            text="Two standard deviations on each side means roughly ninety five percent of totals land between eighty six and one hundred twenty four."
        ) as tracker:
            self.play(FadeIn(result), run_time=tracker.duration)

        self.wait(0.3)
        self.play(FadeOut(steps), FadeOut(result), FadeOut(case_title))

        # ---------------- 5. Summary ----------------
        s1 = Tex("Key point: sums, not single rolls, become normal.")
        s2 = Tex("Careful: the spread grows like the square root of n.")
        s3 = Tex("Quiz: what is the standard deviation for 100 dice?")
        summary = VGroup(s1, s2, s3).arrange(DOWN, buff=0.6)
        for item in summary:
            item.scale_to_fit_width(config.frame_width * 0.85)

        with self.voiceover(
            text="Remember, it is the sum that becomes normal, and its spread grows like the square root of n. Try this: what is the standard deviation for one hundred dice?"
        ) as tracker:
            self.play(FadeIn(s1), FadeIn(s2), FadeIn(s3), run_time=tracker.duration)

        answer = Tex("Answer: about 17.1").scale(0.9).next_to(summary, DOWN, buff=0.6)

        with self.voiceover(
            text="The answer is the square root of one hundred times thirty five over twelve, about seventeen point one."
        ) as tracker:
            self.play(Write(answer), run_time=tracker.duration)

        self.wait(1)