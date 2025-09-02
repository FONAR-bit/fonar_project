document.addEventListener("DOMContentLoaded", function () {
    function toggleFields(row) {
        const tipoField = row.querySelector("select[id$='-tipo']");
        if (!tipoField) return;

        const prestamoField = row.querySelector("select[id$='-prestamo']").closest("td");
        const cuotaField = row.querySelector("select[id$='-cuota']").closest("td");
        const capitalField = row.querySelector("input[id$='-capital']").closest("td");
        const interesField = row.querySelector("input[id$='-interes']").closest("td");
        const cuotaPagadaField = row.querySelector("input[id$='-cuota_pagada']").closest("td");

        function updateVisibility() {
            if (tipoField.value === "aporte") {
                prestamoField.style.display = "none";
                cuotaField.style.display = "none";
                capitalField.style.display = "none";
                interesField.style.display = "none";
                cuotaPagadaField.style.display = "none";
            } else if (tipoField.value === "prestamo") {
                prestamoField.style.display = "";
                cuotaField.style.display = "";
                capitalField.style.display = "";
                interesField.style.display = "";
                cuotaPagadaField.style.display = "";
            } else {
                prestamoField.style.display = "none";
                cuotaField.style.display = "none";
                capitalField.style.display = "none";
                interesField.style.display = "none";
                cuotaPagadaField.style.display = "none";
            }
        }

        tipoField.addEventListener("change", updateVisibility);
        updateVisibility();

        // 🔄 Filtrar cuotas al cambiar préstamo
        const prestamoSelect = row.querySelector("select[id$='-prestamo']");
        const cuotaSelect = row.querySelector("select[id$='-cuota']");

        if (prestamoSelect && cuotaSelect) {
            prestamoSelect.addEventListener("change", function () {
                const prestamoId = this.value;
                cuotaSelect.innerHTML = "<option value=''>---------</option>"; // reset

                if (prestamoId) {
                    fetch(`/cuotas/${prestamoId}/`)
                        .then(response => response.json())
                        .then(data => {
                            data.forEach(c => {
                                const opt = document.createElement("option");
                                opt.value = c.id;
                                opt.textContent = c.texto;
                                cuotaSelect.appendChild(opt);
                            });
                        });
                }
            });
        }
    }

    // Inicializar todas las filas ya cargadas
    document.querySelectorAll(".dynamic-pagoaplicacion_set").forEach(toggleFields);

    // Detectar nuevas filas agregadas dinámicamente
    document.body.addEventListener("click", function (e) {
        if (e.target && e.target.classList.contains("add-row")) {
            setTimeout(function () {
                document.querySelectorAll(".dynamic-pagoaplicacion_set").forEach(toggleFields);
            }, 200);
        }
    });
});
