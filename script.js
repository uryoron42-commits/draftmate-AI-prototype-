const generateButton = document.getElementById("generateButton");
const instructionsInput = document.getElementById("instructions");
const outputArea = document.getElementById("output");
const skillSelector = document.querySelector("select");
const downloadPdfButton = document.getElementById("downloadPdfButton");

let generatedContent = "";

const documentUpload = document.getElementById("documentUpload");
const uploadStatus = document.getElementById("uploadStatus");

let uploadedDocumentText = "";
documentUpload.addEventListener("change", async function () {
    const file = documentUpload.files[0];

    uploadedDocumentText = "";

    if (!file) {
        uploadStatus.textContent = "No document selected.";
        return;
    }

    if (!file.name.toLowerCase().endsWith(".txt")) {
        uploadStatus.textContent = "Please select a .txt file.";
        documentUpload.value = "";
        return;
    }

    if (file.size > 1_000_000) {
        uploadStatus.textContent = "File is too large. Maximum size is 1 MB.";
        documentUpload.value = "";
        return;
    }

    try {
        uploadedDocumentText = await file.text();

        if (!uploadedDocumentText.trim()) {
            uploadedDocumentText = "";
            uploadStatus.textContent = "The selected file is empty.";
            return;
        }

        uploadStatus.textContent =
            `Loaded: ${file.name} (${file.size.toLocaleString()} bytes)`;

    } catch (error) {
        console.error(error);
        uploadedDocumentText = "";
        uploadStatus.textContent = "Could not read this file.";
    }
});

generateButton.addEventListener("click", async function () {
    const instructions = instructionsInput.value.trim();
    const skill = skillSelector.value;

    if (!instructions) {
        outputArea.textContent = "Please enter your instructions first.";
        return;
    }

    generateButton.disabled = true;
    downloadPdfButton.disabled = true;
    outputArea.textContent = "DraftMate AI is generating your response...";

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/api/generate",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    instructions: instructions,
                    skill: skill,
                    document_text: uploadedDocumentText
                })
            }
        );

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const data = await response.json();

        generatedContent = data.result;
        outputArea.textContent = generatedContent;
        downloadPdfButton.disabled = !generatedContent.trim();

    } catch (error) {
        console.error(error);
        generatedContent = "";
        outputArea.textContent =
            "Generation failed. Check that the Python server is running.";
    } finally {
        generateButton.disabled = false;
    }
});


downloadPdfButton.addEventListener("click", async function () {
    if (!generatedContent.trim()) {
        return;
    }

    downloadPdfButton.disabled = true;
    downloadPdfButton.textContent = "Preparing PDF...";

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/api/download-pdf",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    title: "DraftMate AI Document",
                    content: generatedContent
                })
            }
        );

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const pdfBlob = await response.blob();
        const downloadUrl = URL.createObjectURL(pdfBlob);
        const link = document.createElement("a");

        link.href = downloadUrl;
        link.download = "DraftMate_Document.pdf";

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(downloadUrl);

    } catch (error) {
        console.error(error);
        alert("PDF download failed. Check the Python terminal.");
    } finally {
        downloadPdfButton.disabled = false;
        downloadPdfButton.textContent = "Download as PDF";
    }
});