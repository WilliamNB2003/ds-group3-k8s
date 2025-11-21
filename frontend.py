frontpage_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Yoda Fortune Cookie</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            /* Yoda green/earthy gradient */
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            padding: 50px 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            text-align: center;
            max-width: 500px;
            width: 100%;
        }
        
        h1 {
            color: #333;
            margin-bottom: 30px;
            font-size: 2em;
        }
        
        .cookie {
            width: 150px;
            height: auto;
            margin-bottom: 20px;
            filter: drop-shadow(0 10px 15px rgba(0,0,0,0.2));
            transition: transform 0.3s ease;
        }

        .cookie:hover {
            transform: scale(1.1) rotate(5deg);
        }
        
        #fortune {
            font-size: 1.2em;
            color: #555;
            min-height: 60px;
            margin-bottom: 30px;
            font-style: italic;
            line-height: 1.6;
        }
        
        button {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            font-size: 1.1em;
            border-radius: 50px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            font-weight: 600;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(17, 153, 142, 0.4);
        }
        
        button:active {
            transform: translateY(0);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Fortune Cookie</h1>
        
        <img src="/static/yoda.jpg" alt="Yoda holding a fortune cookie" class="cookie">
        
        <div id="fortune">Click the button, you must!</div>
        <button onclick="getCookie()">Get Fortune</button>
    </div>

    <script>
        async function getCookie() {
            try {
                console.log("in get cookie");
                const response = await fetch('/get_cookie');
                const data = await response.json();
                const cookie = data;
                console.log("cookie", cookie);
                
                const fortuneElement = document.getElementById('fortune');
                
                // Simple fade effect
                fortuneElement.style.opacity = 0;
                setTimeout(() => {
                    fortuneElement.textContent = cookie || 'No fortune found!';
                    fortuneElement.style.opacity = 1;
                }, 200);
                
            } catch (error) {
                document.getElementById('fortune').textContent = 'Error getting fortune!';
                console.error(error);
            }
        }
    </script>
</body>
</html>'''