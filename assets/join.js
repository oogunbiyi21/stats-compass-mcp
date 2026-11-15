// Early-access sign-ups: each form posts the visitor's email to Buttondown in a new tab
// (Buttondown sends the confirmation email), and this page says what happens next.
for (const form of document.querySelectorAll("form[data-join]")) {
  form.addEventListener("submit", () => setTimeout(() => {
    form.style.display = "none";  // its flex class would outrank [hidden]
    const done = document.getElementById(form.dataset.join);
    if (done) done.hidden = false;
  }));
}
