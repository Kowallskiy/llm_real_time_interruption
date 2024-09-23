https://github.com/user-attachments/assets/8643b1bc-a9ae-4b66-8592-791244083fe9

____
## Project Description

The idea of the project is to build a chatbot that can interrupt the user in real-time by remembering previous conversations related to particular topics and their associated sentiment. The AI can interrupt the user while they are still typing because of how the inference code was implemented.

To deploy the project on AWS, services like __ECS__, __ECR__, __SageMaker__, __CloudWatch__, and __Fargate__ technology were used. Three NLP models were deployed on different __SageMaker__ endpoints, and these endpoints were invoked in the _app.py_ file hosted on __Fargate__ in the __Elastic Container Service__.
