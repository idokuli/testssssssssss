from flask import Blueprint, request, redirect, url_for, session, render_template, flash
from s3_service import S3Service  # Assumes s3_service.py is in your root folder

s3_bp = Blueprint('s3', __name__)

def get_worker():
    """Helper to initialize the S3 Service from session data."""
    return S3Service(
        session.get('access'), 
        session.get('secret'), 
        session.get('region')
    )

@s3_bp.route('/')
def s3_index():
    if 'access' not in session:
        return redirect(url_for('s3.s3_login'))
    
    try:
        worker = get_worker()
        # Your original logic to list files
        _, files = worker.list_files(session['bucket'])
        
        # We now pass the data to a separate HTML file instead of a string
        return render_template('s3_explorer.html', 
                               files=files, 
                               bucket_name=session['bucket'])
    except Exception as e:
        flash(f"S3 Error: {str(e)}")
        return redirect(url_for('s3.s3_logout'))

@s3_bp.route('/login', methods=['GET', 'POST'])
def s3_login():
    if request.method == 'POST':
        # Store credentials in session
        session.update({
            'access': request.form.get('access'),
            'secret': request.form.get('secret'),
            'region': request.form.get('region', 'us-east-1'),
            'bucket': request.form.get('bucket')
        })
        return redirect(url_for('s3.s3_index'))
    
    return render_template('s3_login.html')

@s3_bp.route('/logout')
def s3_logout():
    # Clear S3 specific session data
    for key in ['access', 'secret', 'region', 'bucket']:
        session.pop(key, None)
    return redirect(url_for('hub')) # Returns to the main dashboard