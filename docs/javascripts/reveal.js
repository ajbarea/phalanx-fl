/* Scroll-reveal for landing page sections and hero-page body class */
document.addEventListener("DOMContentLoaded", function () {
  /* Mark the homepage so CSS can target it (hide default footer, etc.) */
  if (document.querySelector(".hero")) {
    document.documentElement.classList.add("hero-page");
    document.body.classList.add("hero-page");
  }

  /* IntersectionObserver — fade-in landing sections on scroll */
  var sections = document.querySelectorAll(".landing-section");
  if (!sections.length) return;

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  sections.forEach(function (section) {
    observer.observe(section);
  });
});
