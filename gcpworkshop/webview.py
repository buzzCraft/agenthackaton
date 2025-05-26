from flask import Flask, render_template_string, request, jsonify, Response
import markdown2
from graph import web_search_report
import time
import queue
import threading
import uuid
import json

app = Flask(__name__)

# Store for active report generation sessions
sessions = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Search Report</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: sans-serif; margin: 2rem; line-height: 1.6; max-width: 1200px; margin: 0 auto; }
        h1, h2, h3 { color: #333; }
        code { background: #f5f5f5; padding: 0.2em 0.4em; border-radius: 4px; }

        #spinner {
            display: none;
            margin: 2rem 0;
            font-size: 1.2rem;
            color: #555;
        }

        .spinner-icon {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-right: 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        #report-container {
            margin-top: 2rem;
        }

        input[type="text"] {
            padding: 0.5rem;
            font-size: 1rem;
            width: 300px;
        }

        button {
            padding: 0.5rem 1rem;
            font-size: 1rem;
        }
        
        #status {
            margin: 1rem 0;
            padding: 1rem;
            background-color: #f5f5f5;
            border-left: 4px solid #3498db;
            display: none;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .header-image {
            width: 100%;
            max-height: 300px;
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 2rem;
        }
        
        .image-caption {
            font-style: italic;
            text-align: center;
            margin-top: -1.5rem;
            margin-bottom: 2rem;
            color: #666;
            font-size: 0.9rem;
        }
        
        .report-title {
            text-align: center;
            margin-bottom: 0.5rem;
        }
        
        .report-date {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <h1>Web Search Report</h1>
    <form id="search-form">
        <input type="text" name="query" placeholder="What company do you want to research?" required>
        <button type="submit">Search</button>
    </form>

    <div id="spinner">
        <div class="spinner-icon"></div>
        <span id="status-text">Initializing...</span>
    </div>
    
    <div id="status"></div>

    <div id="report-container"></div>

    <script>
        document.getElementById("search-form").addEventListener("submit", function(e) {
            e.preventDefault();
            const query = e.target.query.value;
            const statusDiv = document.getElementById("status");
            
            document.getElementById("spinner").style.display = "block";
            statusDiv.style.display = "block";
            document.getElementById("report-container").innerHTML = "";
            statusDiv.innerHTML = "";

            // First, start a new session
            fetch(`/start_report?query=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    const sessionId = data.session_id;
                    
                    // Connect to the event stream for this session
                    const eventSource = new EventSource(`/status/${sessionId}`);
                    
                    eventSource.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        
                        if (data.status === "complete") {
                            // Report is complete
                            document.getElementById("spinner").style.display = "none";
                            
                            // Create header container
                            const reportContainer = document.getElementById("report-container");
                            
                            // Add header image if available
                            if (data.header_image) {
                                const headerImage = document.createElement("img");
                                headerImage.src = `data:image/png;base64,${data.header_image}`;
                                headerImage.className = "header-image";
                                headerImage.alt = "Report header image";
                                reportContainer.appendChild(headerImage);
                                
                                if (data.image_prompt) {
                                    const imageCaption = document.createElement("div");
                                    imageCaption.className = "image-caption";
                                    imageCaption.textContent = `Image: "${data.image_prompt}"`;
                                    reportContainer.appendChild(imageCaption);
                                }
                            }
                            
                            // Create report title
                            const title = document.createElement("h1");
                            title.className = "report-title";
                            title.textContent = `${query} - News Report`;
                            reportContainer.appendChild(title);
                            
                            // Add date
                            const date = document.createElement("div");
                            date.className = "report-date";
                            date.textContent = new Date().toLocaleDateString('en-US', {
                                weekday: 'long',
                                year: 'numeric',
                                month: 'long',
                                day: 'numeric'
                            });
                            reportContainer.appendChild(date);
                            
                            // Add the report content
                            const reportContent = document.createElement("div");
                            reportContent.innerHTML = data.report;
                            reportContainer.appendChild(reportContent);
                            
                            eventSource.close();
                        } else {
                            // Update status
                            document.getElementById("status-text").innerText = data.message;
                            
                            // Add to status log
                            const statusItem = document.createElement("div");
                            statusItem.textContent = `${new Date().toLocaleTimeString()}: ${data.message}`;
                            statusDiv.appendChild(statusItem);
                            statusDiv.scrollTop = statusDiv.scrollHeight;
                        }
                    };
                    
                    eventSource.onerror = function() {
                        console.error("EventSource failed");
                        document.getElementById("status-text").innerText = "Connection lost";
                        eventSource.close();
                    };
                });
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/start_report")
def start_report():
    query = request.args.get("query", "")
    if not query:
        return jsonify({"error": "No query provided"})
    
    # Create a unique session ID
    session_id = str(uuid.uuid4())
    
    # Create a message queue for this session
    message_queue = queue.Queue()
    
    # Store session info
    sessions[session_id] = {
        "query": query,
        "queue": message_queue,
        "report": None,
        "header_image": None,
        "image_prompt": None
    }
    
    # Start report generation in a background thread
    def generate_report():
        def status_callback(message):
            message_queue.put(message)
        
        result = web_search_report(query, 10, time="week", status_callback=status_callback)
        report_html = markdown2.markdown(result["report"])
        
        sessions[session_id]["report"] = report_html
        sessions[session_id]["header_image"] = result["header_image"]
        sessions[session_id]["image_prompt"] = result["image_prompt"]
        message_queue.put("complete")
    
    thread = threading.Thread(target=generate_report)
    thread.daemon = True
    thread.start()
    
    return jsonify({"session_id": session_id})

@app.route("/status/<session_id>")
def status_stream(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Invalid session ID"}), 404
    
    def generate():
        session_data = sessions[session_id]
        queue_obj = session_data["queue"]
        
        while True:
            message = queue_obj.get()
            
            if message == "complete":
                data = {
                    "status": "complete",
                    "report": session_data["report"],
                    "header_image": session_data["header_image"],
                    "image_prompt": session_data["image_prompt"]
                }
                yield f"data: {json.dumps(data)}\n\n"
                break
            
            data = {
                "status": "progress",
                "message": message
            }
            yield f"data: {json.dumps(data)}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, threaded=True)