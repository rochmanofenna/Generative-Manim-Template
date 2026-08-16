from manim import *
from math import *
import numpy as np
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


class GenScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))

        # ---------------- Section 1: Concept Definition ----------------
        title = Tex("The Pythagorean Theorem").scale(1.2).to_edge(UP)
        definition = Tex(
            "In a right triangle, the square on the hypotenuse equals "
            "the sum of the squares on the two legs."
        )
        definition.scale_to_fit_width(config.frame_width * 0.9)
        definition.next_to(title, DOWN, buff=0.8)

        with self.voiceover(
            text="The Pythagorean theorem says that in a right triangle, the square on the longest side equals the sum of the squares on the two shorter sides."
        ) as tracker:
            self.play(Write(title), FadeIn(definition), run_time=tracker.duration)

        # ---------------- Section 2: Formula Breakdown ----------------
        formula = MathTex("a^2", "+", "b^2", "=", "c^2").scale(1.6)
        formula.next_to(definition, DOWN, buff=1.0)

        with self.voiceover(
            text="In symbols: a squared plus b squared equals c squared, where a and b are the legs and c is the hypotenuse."
        ) as tracker:
            self.play(Write(formula), run_time=tracker.duration)

        with self.voiceover(
            text="Let us prove it with nothing but four copies of the same right triangle."
        ) as tracker:
            self.play(
                FadeOut(definition), FadeOut(formula), FadeOut(title),
                run_time=tracker.duration
            )

        # ---------------- Section 3: The construction ----------------
        a, b = 2.2, 1.4
        s = a + b
        k = 0.9

        def pt(x, y):
            return np.array([k * (x - s / 2.0), k * (y - s / 2.0) - 0.4, 0.0])

        outer = Polygon(pt(0, 0), pt(s, 0), pt(s, s), pt(0, s),
                        color=WHITE, stroke_width=4)

        head = Tex("A big square of side a plus b").scale(0.8).to_edge(UP)
        side_lab1 = MathTex("a").scale(0.8).next_to(
            Line(pt(0, 0), pt(a, 0)), DOWN, buff=0.15)
        side_lab2 = MathTex("b").scale(0.8).next_to(
            Line(pt(a, 0), pt(s, 0)), DOWN, buff=0.15)

        with self.voiceover(
            text="Start with a big square whose side is a plus b."
        ) as tracker:
            self.play(Write(head), Create(outer),
                      FadeIn(side_lab1), FadeIn(side_lab2),
                      run_time=tracker.duration)

        # Arrangement 1: four triangles around a tilted square
        t1 = Polygon(pt(0, 0), pt(a, 0), pt(0, b), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        t2 = Polygon(pt(s, 0), pt(s, a), pt(a, 0), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        t3 = Polygon(pt(s, s), pt(b, s), pt(s, a), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        t4 = Polygon(pt(0, s), pt(0, b), pt(b, s), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        tris = VGroup(t1, t2, t3, t4)

        csq = Polygon(pt(a, 0), pt(s, a), pt(b, s), pt(0, b), color=WHITE,
                      fill_color=BLUE, fill_opacity=0.6, stroke_width=2)
        clab = MathTex("c^2").scale(1.1).move_to(pt(s / 2.0, s / 2.0))

        with self.voiceover(
            text="Place four identical right triangles in the corners. The white space left in the middle is a tilted square whose side is the hypotenuse c."
        ) as tracker:
            self.play(FadeIn(tris), run_time=tracker.duration)

        with self.voiceover(
            text="So the uncovered area equals c squared."
        ) as tracker:
            self.play(FadeIn(csq), Write(clab), run_time=tracker.duration)

        # ---------------- Section 4: Rearrangement ----------------
        u1 = Polygon(pt(0, 0), pt(a, 0), pt(a, b), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        u2 = Polygon(pt(0, 0), pt(a, b), pt(0, b), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        u3 = Polygon(pt(a, b), pt(s, b), pt(s, s), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)
        u4 = Polygon(pt(a, b), pt(s, s), pt(a, s), color=WHITE,
                     fill_color=RED, fill_opacity=0.8, stroke_width=2)

        asq = Polygon(pt(0, b), pt(a, b), pt(a, s), pt(0, s), color=WHITE,
                      fill_color=GREEN, fill_opacity=0.6, stroke_width=2)
        bsq = Polygon(pt(a, 0), pt(s, 0), pt(s, b), pt(a, b), color=WHITE,
                      fill_color=YELLOW, fill_opacity=0.6, stroke_width=2)
        alab = MathTex("a^2").scale(1.0).move_to(pt(a / 2.0, b + a / 2.0))
        blab = MathTex("b^2").scale(0.9).move_to(pt(a + b / 2.0, b / 2.0))

        with self.voiceover(
            text="Now slide the very same four triangles into new positions inside the same big square."
        ) as tracker:
            self.play(
                FadeOut(csq), FadeOut(clab),
                Transform(t1, u1), Transform(t2, u2),
                Transform(t3, u3), Transform(t4, u4),
                run_time=tracker.duration
            )

        with self.voiceover(
            text="The uncovered space is now two squares: one of side a and one of side b. Same big square, same four triangles, so the leftover areas must be equal."
        ) as tracker:
            self.play(FadeIn(asq), FadeIn(bsq), Write(alab), Write(blab),
                      run_time=tracker.duration)

        conclusion = MathTex("a^2", "+", "b^2", "=", "c^2").scale(1.3)
        conclusion.to_edge(DOWN)

        with self.voiceover(
            text="Therefore a squared plus b squared equals c squared. The theorem is proved."
        ) as tracker:
            self.play(Write(conclusion), run_time=tracker.duration)

        old = VGroup(head, outer, tris, asq, bsq, alab, blab,
                     side_lab1, side_lab2, conclusion)

        # ---------------- Section 5: Real-World Case Study ----------------
        case_title = Tex("Case study: a ladder against a wall").scale(0.9).to_edge(UP)
        step1 = MathTex("a = 3 \\text{ m}, \\quad b = 4 \\text{ m}").scale(1.0)
        step2 = MathTex("3^2 + 4^2 = 9 + 16 = 25").scale(1.0)
        step3 = MathTex("c = \\sqrt{25} = 5 \\text{ m}").scale(1.0)
        steps = VGroup(step1, step2, step3).arrange(DOWN, buff=0.6)
        steps.next_to(case_title, DOWN, buff=0.8)

        with self.voiceover(
            text="A ladder leans on a wall. Its foot is three meters out and it reaches four meters up."
        ) as tracker:
            self.play(FadeOut(old), FadeIn(case_title), Write(step1),
                      run_time=tracker.duration)

        with self.voiceover(
            text="Three squared plus four squared is nine plus sixteen, which is twenty five. The square root of twenty five is five, so the ladder is five meters long."
        ) as tracker:
            self.play(Write(step2), Write(step3), run_time=tracker.duration)

        # ---------------- Section 6: Summary ----------------
        summary = VGroup(
            Tex("Key idea: same big square, same four triangles, equal leftovers."),
            Tex("Careful: the theorem holds only for right triangles."),
            Tex("Try it: legs 5 and 12 give a hypotenuse of 13."),
        ).arrange(DOWN, buff=0.6)
        summary.scale_to_fit_width(config.frame_width * 0.9)

        with self.voiceover(
            text="To summarize: the same big square with the same four triangles forces the leftover areas to match. Remember, this only works for right triangles."
        ) as tracker:
            self.play(FadeOut(case_title), FadeOut(steps),
                      FadeIn(summary), run_time=tracker.duration)

        self.wait(2)