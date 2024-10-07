from setuptools import setup, find_packages
import os

# Automatically locate the home directory and append '.yac/config/'
home_dir = os.path.expanduser("~/.yac/config/")

# Ensure the home directory exists
if not os.path.exists(home_dir):
    os.makedirs(home_dir)

# Read the README.md for the long description
def readme():
    with open('README.md', 'r', encoding='utf-8') as f:
        return f.read()

setup(
    name='yachecker',                                # Package name
    version='1.0.2',                           # Version of the package
    description='YAC: Yes Another Checker',     # Short description
    long_description=readme(),                 # Long description from README.md
    long_description_content_type='text/markdown',
    author='Ali Emara',                        # Your name
    author_email='ali.emara175@gmail.com',     # Your email
    url='https://github.com/hithmast/YAC.git', # URL of your project
    packages=find_packages(),                  # Automatically find package directories
    install_requires=[                         # Dependencies (from requirements.txt)
        'requests',
        'argparse',
        'urllib3',
    ],
    include_package_data=True,                 # Include non-Python files like config.ini
    data_files=[                               # Install config file under ~/.yac/config
        (home_dir, ['config/websites_config.ini'])
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    entry_points={                             # Entry points for command line execution
        'console_scripts': [
            'yac=yac.main:main',               # Creates a 'yac' command to execute the script
        ],
    },
    python_requires='>=3.6',                   # Minimum Python version required
)
