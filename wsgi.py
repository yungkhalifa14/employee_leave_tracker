from waitress import serve
from webapp import app

if __name__ == '__main__':
    print("Starting production server on http://0.0.0.0:5001")
    serve(app, host='0.0.0.0', port=5001)
