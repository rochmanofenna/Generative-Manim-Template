from manim import *
from math import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


class GenScene(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))

        # ---------- 1. Concept Definition ----------
        title = Tex(
            "Fourier Series: any periodic signal is a sum of sine waves"
        ).scale_to_fit_width(config.frame_width * 0.9)

        with self.voiceover(
            text="A Fourier series rebuilds any periodic signal as a sum of simple sine waves."
        ) as tracker:
            self.play(Write(title), run_time=tracker.duration)

        with self.voiceover(
            text="Let us use it to build a square wave, a signal that jumps between plus one and minus one."
        ) as tracker:
            self.play(title.animate.to_edge(UP), run_time=tracker.duration)

        self.play(FadeOut(title))

        # ---------- 2. Formula Breakdown ----------
        formula = MathTex(
            r"f(x)=\frac{4}{\pi}\left(\frac{\sin x}{1}+\frac{\sin 3x}{3}"
            r"+\frac{\sin 5x}{5}+\cdots\right)"
        ).scale_to_fit_width(config.frame_width * 0.8)

        note = Tex("Only odd harmonics, amplitude falls as one over k").next_to(
            formula, DOWN, buff=0.6
        )

        with self.voiceover(
            text="Here is the recipe. Only the odd harmonics appear, and each one has an amplitude of one over k."
        ) as tracker:
            self.play(Write(formula), run_time=tracker.duration)

        with self.voiceover(
            text="The leading factor four over pi scales the whole sum to reach a height of one."
        ) as tracker:
            self.play(FadeIn(note), run_time=tracker.duration)

        self.play(FadeOut(formula), FadeOut(note))

        # ---------- 3. Chart: convergence ----------
        axes = Axes(
            x_range=[-PI, 3 * PI, PI],
            y_range=[-1.6, 1.6, 1],
            x_length=11,
            y_length=4.2,
            axis_config={"include_tip": False},
        ).scale(0.8).to_edge(DOWN, buff=0.7)

        target = axes.plot(
            lambda x: 1.0 if sin(x) > 0 else -1.0,
            color=GREY_B,
            use_smoothing=False,
            discontinuities=[-PI, 0, PI, 2 * PI, 3 * PI],
        )

        def partial(n):
            def f(x):
                s = 0.0
                k = 1
                while k <= n:
                    s += sin(k * x) / k
                    k += 2
                return 4 / pi * s
            return axes.plot(f, color=YELLOW)

        label = MathTex(r"N=1").scale(0.9).to_corner(UL)

        with self.voiceover(
            text="Start with a single sine wave. It is smooth and rounded, far from a square."
        ) as tracker:
            self.play(
                Create(axes), Create(target), Create(partial(1)), FadeIn(label),
                run_time=tracker.duration,
            )

        curve = partial(1)
        self.add(curve)

        for n in [3, 7, 15, 31]:
            new_curve = partial(n)
            new_label = MathTex(r"N=" + str(n)).scale(0.9).to_corner(UL)
            with self.voiceover(
                text="Adding the next odd harmonics flattens the tops and sharpens the jumps."
            ) as tracker:
                self.play(
                    Transform(curve, new_curve),
                    Transform(label, new_label),
                    run_time=tracker.duration,
                )

        self.play(FadeOut(axes), FadeOut(target), FadeOut(curve), FadeOut(label))

        # ---------- 4. Real-World Case Study ----------
        head = Tex("Case study: evaluate the series at x equal to pi over two").scale_to_fit_width(
            config.frame_width * 0.85
        ).to_edge(UP)

        step1 = MathTex(r"f\left(\frac{\pi}{2}\right)=\frac{4}{\pi}\left(1-\frac{1}{3}"
                        r"+\frac{1}{5}-\frac{1}{7}+\cdots\right)").scale(0.8)
        step2 = MathTex(r"1-\frac{1}{3}+\frac{1}{5}-\frac{1}{7}=0.7238").scale(0.8)
        step3 = MathTex(r"\frac{4}{\pi}\times 0.7854 = 1.0000").scale(0.8)

        group = VGroup(step1, step2, step3).arrange(DOWN, buff=0.6).next_to(head, DOWN, buff=0.7)

        with self.voiceover(
            text="Check it with numbers. At x equal to pi over two, every sine term is plus or minus one."
        ) as tracker:
            self.play(FadeIn(head), Write(step1), run_time=tracker.duration)

        with self.voiceover(
            text="Four terms give zero point seven two four. More terms creep toward pi over four."
        ) as tracker:
            self.play(Write(step2), run_time=tracker.duration)

        with self.voiceover(
            text="Multiplying by four over pi gives exactly one, the true height of the square wave."
        ) as tracker:
            self.play(Write(step3), run_time=tracker.duration)

        self.play(FadeOut(head), FadeOut(group))

        # ---------- 5. Summary ----------
        s1 = Tex("Key idea: odd sine harmonics with one over k amplitudes build a square wave.")
        s2 = Tex("Watch out: near each jump a nine percent overshoot never vanishes.")
        s3 = Tex("That stubborn spike is called the Gibbs phenomenon.")
        summary = VGroup(s1, s2, s3).arrange(DOWN, buff=0.7)
        summary.scale_to_fit_width(config.frame_width * 0.9)

        with self.voiceover(
            text="To summarize, odd harmonics with one over k amplitudes assemble a square wave."
        ) as tracker:
            self.play(FadeIn(s1), run_time=tracker.duration)

        with self.voiceover(
            text="But near each jump a nine percent overshoot survives forever. That is the Gibbs phenomenon."
        ) as tracker:
            self.play(FadeIn(s2), FadeIn(s3), run_time=tracker.duration)

        self.wait(1)