from glob import glob

from setuptools import setup

package_name = "harmoni_nodes"

setup(
    name=package_name,
    version="2.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Micol Spitale",
    maintainer_email="micol.spitale@gmail.com",
    description="ROS2 nodes of HARMONI (service server and tree runner)",
    license="MIT",
    entry_points={
        "console_scripts": [
            "harmoni_service = harmoni_nodes.service_node:main",
            "harmoni_tree = harmoni_nodes.tree_node:main",
            "harmoni_monitor = harmoni_nodes.monitor:main",
        ],
    },
)
