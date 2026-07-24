cmake_minimum_required(VERSION 3.8)
project(bacs_scheduler)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ConstraintCandidate.msg"
  "msg/SelectedConstraint.msg"
  "msg/RadioStats.msg"
  DEPENDENCIES builtin_interfaces geometry_msgs
)

# Python package (the node) — depends on the bacs_sim package being importable.
ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  bacs_scheduler/bacs_scheduler_node.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
