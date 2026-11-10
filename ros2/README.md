# HARMONI on ROS 2

ROS 2 (Jazzy) layer of HARMONI: it runs the tree files and service backends of `../core`.

| Path | What |
|------|------|
| `harmoni.sh` | docker helper, use it as `./harmoni.sh ros2 <command>` from the repository root |
| `docker/` | ROS 2 image (build context: the repository root) |
| `docker-compose.yml` | `harmoni_ros2` container (+ `harmoni_nao_bridge` with `--nao`) |
| `config/` | which backend serves each service and which tree runs (real and mock setups) |
| `src/harmoni_interfaces` | the `Harmoni` action |
| `src/harmoni_nodes` | `harmoni_service`, `harmoni_tree`, `harmoni_monitor` nodes and the launch file |
| `nao_bridge/` | python 2 HTTP bridge to the NAO robot (NAOqi SDK), no ROS |
| `tests/` | unit tests with a faked rclpy, and the end-to-end smoke test on real ROS 2 |

Quickstart: `doc/quickstart/ROS2-Quickstart.md`.
