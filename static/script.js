console.log("Static JS is loaded!");
document.addEventListener("DOMContentLoaded", function () {
    const roleSelect = document.getElementById("role");
    const skillField = document.getElementById("skill-field");

    if (!roleSelect || !skillField) {
        return;
    }

    function toggleSkillField() {
        const skillInput = skillField.querySelector('input[name="skill"]');
        if (roleSelect.value === "technician") {
            skillField.style.display = "block";
            if (skillInput) {
                skillInput.required = true;
            }
        } else {
            skillField.style.display = "none";
            if (skillInput) {
                skillInput.required = false;
                skillInput.value = "";
            }
        }
    }

    toggleSkillField();
    roleSelect.addEventListener("change", toggleSkillField);
});
