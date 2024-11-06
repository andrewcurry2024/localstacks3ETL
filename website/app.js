(function ($) {

    // Check for existing URLs in localStorage and set the form inputs
    let functionUrlPresign = localStorage.getItem("functionUrlPresign");
    if (functionUrlPresign) {
        $("#functionUrlPresign").val(functionUrlPresign);
    }

    let functionUrlList = localStorage.getItem("functionUrlList");
    if (functionUrlList) {
        console.log("function url list is", functionUrlList);
        $("#functionUrlList").val(functionUrlList);
    }

    let imageItemTemplate = Handlebars.compile($("#image-item-template").html());

    // Function to load API URLs
    async function loadFromAPI() {
        let baseUrl = `${document.location.protocol}//${document.location.host}`;
        if (baseUrl.indexOf("file://") >= 0) {
            baseUrl = `http://localhost:4566`;
        }
        baseUrl = baseUrl.replace("://webapp.s3.", "://").replace("://webapp.s3-website.", "://");

        const headers = { authorization: "AWS4-HMAC-SHA256 Credential=test/20231004/us-east-1/lambda/aws4_request, ..." };

        const loadUrl = async (funcName, resultElement) => {
            const url = `${baseUrl}/2021-10-31/functions/${funcName}/urls`;
            const result = await $.ajax({ url, headers }).promise();
            const funcUrl = JSON.parse(result).FunctionUrlConfigs[0].FunctionUrl;
            $(`#${resultElement}`).val(funcUrl);
            localStorage.setItem(resultElement, funcUrl);
        };

        await loadUrl("presign", "functionUrlPresign");
        await loadUrl("list", "functionUrlList");

        alert("Function URL configurations loaded");
    }

    // Call loadFromAPI function on page load
    loadFromAPI();

    // Form submission handler for loading, saving, and clearing URLs
    $("#configForm").submit(async function (event) {
        event.preventDefault();

        let action = $(this).find("button[type=submit]:focus").attr('name');
        if (action === undefined) {
            // fallback to manually retrieving the submitter from the original event
            action = event.originalEvent.submitter.getAttribute('name');
        }

        if (action == "load") {
            // Trigger loadFromAPI when load button is clicked
            await loadFromAPI();
        } else if (action == "save") {
            // Save the current function URLs to localStorage
            localStorage.setItem("functionUrlPresign", $("#functionUrlPresign").val());
            localStorage.setItem("functionUrlList", $("#functionUrlList").val());
            alert("Configuration saved");
        } else if (action == "clear") {
            // Clear the URLs from localStorage and reset the form
            localStorage.removeItem("functionUrlPresign");
            localStorage.removeItem("functionUrlList");
            $("#functionUrlPresign").val("");
            $("#functionUrlList").val("");
            alert("Configuration cleared");
        } else {
            alert("Unknown action");
        }
    });

    // Upload form submission handler
    $("#uploadForm").submit(function (event) {
        $("#uploadForm button").addClass('disabled');
        event.preventDefault();

        let fileName = $("#customFile").val().replace(/C:\\fakepath\\/i, '');
        let functionUrlPresign = $("#functionUrlPresign").val();

        let urlToCall = functionUrlPresign + "/" + fileName;

        $.ajax({
            url: urlToCall,
            success: function (data) {
                console.log("got pre-signed POST URL", data);

                let fields = data['fields'];
                let formData = new FormData();

                Object.entries(fields).forEach(([field, value]) => {
                    formData.append(field, value);
                });

                // Append file to form data
                const fileElement = document.querySelector("#customFile");
                formData.append("file", fileElement.files[0]);

                $.ajax({
                    type: "POST",
                    url: data['url'],
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function () {
                        alert("success!");
                        updateImageList();
                    },
                    error: function () {
                        alert("error! check the logs");
                    },
                    complete: function (event) {
                        console.log("done", event);
                        $("#uploadForm button").removeClass('disabled');
                    }
                });
            },
            error: function (e) {
                console.log("error", e);
                alert("error getting pre-signed URL. check the logs!");
                $("#uploadForm button").removeClass('disabled');
            }
        });
    });

    // Function to update the image list
    function updateImageList() {
        let listUrl = $("#functionUrlList").val();
        if (!listUrl) {
            alert("Please set the function URL of the list Lambda");
            return;
        }

        $.ajax({
            url: listUrl,
            success: function (response) {
                $('#imagesContainer').empty(); // Empty imagesContainer
                response.forEach(function (item) {
                    console.log(item);
                    let cardHtml = imageItemTemplate(item);
                    $("#imagesContainer").append(cardHtml);
                });
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.log("Error:", textStatus, errorThrown);
                alert("error! check the logs");
            }
        });
    }

    // Trigger image list update when the button is clicked
    $("#updateImageListButton").click(function (event) {
        updateImageList();
    });

    // If the function URL for the list is set, update the image list on page load
    if (functionUrlList) {
        updateImageList();
    }

})(jQuery);
